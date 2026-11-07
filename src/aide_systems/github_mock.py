"""A small GitHub REST mock that turns an opened pull request into a patch.

Agents that fix code by opening a draft PR (instead of calling `propose_patch`) talk to this
server. It implements the Git Data API subset needed to create a branch with changes and open
a pull request: repository, refs, trees, blobs, commits and pulls. When a PR is opened the mock
diffs the PR branch against the base commit and writes a git-format patch, which the fix-track
grader treats exactly like a `propose_patch` submission.

Trees are stored flat (path -> blob) rather than as nested git tree objects. Blob and commit
shas are deterministic content hashes. This is a test double, not a git server.

    aide-github-mock --repo acme/retail --files ./repo --patch-out ./patch.diff --port 8765
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def _sha(*parts: bytes) -> str:
    digest = hashlib.sha1()  # noqa: S324 - content addressing, mirrors git
    for part in parts:
        digest.update(part)
    return digest.hexdigest()


@dataclass
class Pull:
    number: int
    title: str
    body: str
    head: str
    base: str
    draft: bool
    html_url: str


@dataclass
class Repo:
    owner: str
    name: str
    default_branch: str = "main"
    blobs: dict[str, bytes] = field(default_factory=dict)
    trees: dict[str, dict[str, tuple[str, str]]] = field(default_factory=dict)  # sha -> path -> (mode, blob sha)
    commits: dict[str, dict] = field(default_factory=dict)
    refs: dict[str, str] = field(default_factory=dict)
    pulls: list[Pull] = field(default_factory=list)

    def add_blob(self, content: bytes) -> str:
        sha = _sha(b"blob %d\0" % len(content), content)
        self.blobs[sha] = content
        return sha

    def add_tree(self, entries: dict[str, tuple[str, str]]) -> str:
        sha = _sha(json.dumps(sorted(entries.items())).encode())
        self.trees[sha] = entries
        return sha

    def add_commit(self, message: str, tree: str, parents: list[str]) -> str:
        sha = _sha(json.dumps([message, tree, parents]).encode())
        self.commits[sha] = {"message": message, "tree": tree, "parents": parents}
        return sha

    def tree_files(self, tree_sha: str) -> dict[str, bytes]:
        return {path: self.blobs[blob] for path, (_, blob) in self.trees[tree_sha].items()}


def load_repo(owner: str, name: str, files: Path, branch: str = "main") -> Repo:
    repo = Repo(owner, name, default_branch=branch)
    entries = {}
    for path in sorted(p for p in files.rglob("*") if p.is_file()):
        mode = "100755" if path.stat().st_mode & 0o111 else "100644"
        entries[str(path.relative_to(files))] = (mode, repo.add_blob(path.read_bytes()))
    tree = repo.add_tree(entries)
    commit = repo.add_commit("initial snapshot", tree, [])
    repo.refs[f"refs/heads/{branch}"] = commit
    return repo


def diff_between(repo: Repo, base_commit: str, head_commit: str) -> str:
    """A git-format patch turning the base tree into the head tree."""
    base = repo.tree_files(repo.commits[base_commit]["tree"])
    head = repo.tree_files(repo.commits[head_commit]["tree"])
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        env = ["git", "-c", "user.name=aide", "-c", "user.email=aide@example.com", "-C", scratch]
        subprocess.run(["git", "init", "-q", scratch], check=True)
        for path, content in base.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        subprocess.run([*env, "add", "-A"], check=True)
        subprocess.run([*env, "commit", "-q", "-m", "base", "--allow-empty"], check=True)
        for child in root.iterdir():
            if child.name != ".git":
                shutil.rmtree(child) if child.is_dir() else child.unlink()
        for path, content in head.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        subprocess.run([*env, "add", "-A"], check=True)
        return subprocess.run([*env, "diff", "--cached", "--no-color"], check=True, capture_output=True, text=True).stdout


class GithubMock:
    def __init__(self, repo: Repo, patch_path: Path | None = None, host: str = "127.0.0.1", port: int = 0) -> None:
        self.repo = repo
        self.patch_path = patch_path
        self.base_commit = repo.refs[f"refs/heads/{repo.default_branch}"]
        self._lock = threading.Lock()
        mock = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # keep test output quiet
                pass

            def _send(self, status: int, body) -> None:
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                # Real GitHub reports the scopes of a classic token on every response.
                self.send_header("X-OAuth-Scopes", "repo")
                self.end_headers()
                self.wfile.write(data)

            def _route(self, method: str) -> None:
                url = urlparse(self.path)
                length = int(self.headers.get("Content-Length") or 0)
                payload = json.loads(self.rfile.read(length) or b"{}") if length else {}
                if not self.headers.get("Authorization"):
                    return self._send(401, {"message": "Requires authentication"})
                with mock._lock:
                    status, body = mock.handle(method, url.path, parse_qs(url.query), payload)
                self._send(status, body)

            def do_GET(self):
                self._route("GET")

            def do_POST(self):
                self._route("POST")

        self.server = ThreadingHTTPServer((host, port), Handler)
        self.url = f"http://{host}:{self.server.server_address[1]}"

    def start(self) -> str:
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self.url

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    # -- routing ------------------------------------------------------------
    def handle(self, method: str, path: str, query: dict, body: dict) -> tuple[int, object]:
        repo = self.repo
        prefix = f"/repos/{repo.owner}/{repo.name}"
        if not path.startswith(prefix):
            return 404, {"message": "Not Found"}
        rest = path[len(prefix) :]
        if method == "GET" and rest == "":
            return 200, {
                "owner": {"login": repo.owner},
                "default_branch": repo.default_branch,
                "name": repo.name,
                "private": False,
                "archived": False,
                "permissions": {"admin": False, "push": True, "pull": True},
            }
        if method == "GET" and (m := re.fullmatch(r"/git/ref/heads/(.+)", rest)):
            sha = repo.refs.get(f"refs/heads/{m.group(1)}")
            return (200, {"object": {"sha": sha, "type": "commit"}}) if sha else (404, {"message": "Not Found"})
        if method == "GET" and (m := re.fullmatch(r"/git/trees/([0-9a-f]+)", rest)):
            sha = m.group(1)
            tree = repo.commits[sha]["tree"] if sha in repo.commits else sha
            if tree not in repo.trees:
                return 404, {"message": "Not Found"}
            entries = [{"path": p, "type": "blob", "mode": mode, "sha": blob} for p, (mode, blob) in sorted(repo.trees[tree].items())]
            return 200, {"sha": tree, "truncated": False, "tree": entries}
        if method == "POST" and rest == "/git/blobs":
            content = body.get("content", "")
            raw = content.encode() if body.get("encoding", "utf-8") == "utf-8" else __import__("base64").b64decode(content)
            return 201, {"sha": repo.add_blob(raw)}
        if method == "POST" and rest == "/git/trees":
            base = body.get("base_tree")
            base_commit_tree = repo.commits[base]["tree"] if base in repo.commits else base
            entries = dict(repo.trees.get(base_commit_tree, {})) if base else {}
            for item in body.get("tree", []):
                if item.get("sha") is None:
                    entries.pop(item["path"], None)
                else:
                    entries[item["path"]] = (item.get("mode", "100644"), item["sha"])
            return 201, {"sha": repo.add_tree(entries)}
        if method == "POST" and rest == "/git/commits":
            return 201, {"sha": repo.add_commit(body["message"], body["tree"], body.get("parents", []))}
        if method == "POST" and rest == "/git/refs":
            repo.refs[body["ref"]] = body["sha"]
            return 201, {"ref": body["ref"], "object": {"sha": body["sha"]}}
        if method == "GET" and rest == "/pulls":
            head = (query.get("head") or [""])[0].split(":")[-1]
            return 200, [self._pull_json(p) for p in repo.pulls if not head or p.head == head]
        if method == "POST" and rest == "/pulls":
            number = len(repo.pulls) + 1
            pull = Pull(number, body["title"], body.get("body", ""), body["head"], body["base"], bool(body.get("draft")), f"https://github.com/{repo.owner}/{repo.name}/pull/{number}")
            repo.pulls.append(pull)
            self._write_patch(pull)
            return 201, self._pull_json(pull)
        return 404, {"message": "Not Found"}

    def _pull_json(self, pull: Pull) -> dict:
        return {"number": pull.number, "title": pull.title, "html_url": pull.html_url, "draft": pull.draft, "user": {"login": "aide-bench-bot"}}

    def _write_patch(self, pull: Pull) -> None:
        head = self.repo.refs.get(f"refs/heads/{pull.head}")
        if head and self.patch_path:
            self.patch_path.parent.mkdir(parents=True, exist_ok=True)
            self.patch_path.write_text(diff_between(self.repo, self.base_commit, head))

    @property
    def base_sha(self) -> str:
        return self.base_commit


def main() -> None:
    parser = argparse.ArgumentParser(prog="aide-github-mock", description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", default="acme/repo", help="owner/name")
    parser.add_argument("--files", type=Path, required=True, help="directory holding the repository snapshot")
    parser.add_argument("--patch-out", type=Path, required=True, help="where to write the patch when a PR opens")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    owner, name = args.repo.split("/")
    mock = GithubMock(load_repo(owner, name, args.files), args.patch_out, port=args.port)
    print(mock.start(), f"base_sha={mock.base_sha}", flush=True)
    threading.Event().wait()


if __name__ == "__main__":
    main()
