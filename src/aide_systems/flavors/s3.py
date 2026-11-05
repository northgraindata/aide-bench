"""object_storage/s3-minio: buckets and objects, with optional AccessDenied prefixes."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from .base import Flavor
from .registry import register
from .util import clip


@register
class S3Minio(Flavor):
    kind = "object_storage"
    name = "s3-minio"

    @classmethod
    def build(cls, spec: dict, scenario: Path, world: Path) -> None:
        target = world / cls.name
        target.mkdir(parents=True, exist_ok=True)
        for bucket, folder in spec.get("buckets", {}).items():
            shutil.copytree(scenario / folder, target / "buckets" / bucket, dirs_exist_ok=True)
        (target / "denied.json").write_text(json.dumps(spec.get("denied", [])))

    def _denied(self, bucket: str, key: str) -> bool:
        denied = json.loads((self.dir / "denied.json").read_text())
        return any(f"{bucket}/{key}".startswith(prefix) for prefix in denied)

    def tools(self):
        buckets = self.dir / "buckets"

        def s3_list_buckets() -> dict:
            """List buckets."""
            return {"buckets": sorted(p.name for p in buckets.iterdir() if p.is_dir())}

        def s3_list_objects(bucket: str, prefix: str = "", limit: int = 100) -> dict:
            """List objects in a bucket under a prefix, with size and last-modified time."""
            if self._denied(bucket, prefix):
                return {"error": f"AccessDenied: not authorized to list s3://{bucket}/{prefix}"}
            root = buckets / bucket
            if not root.is_dir():
                return {"error": f"NoSuchBucket: {bucket}"}
            objects = []
            for p in sorted(root.rglob("*")):
                if p.is_file():
                    key = str(p.relative_to(root))
                    if key.startswith(prefix):
                        stat = p.stat()
                        objects.append({"key": key, "size": stat.st_size})
            return {"objects": objects[:limit], "truncated": len(objects) > limit}

        def s3_get_object(bucket: str, key: str, max_chars: int = 20000) -> dict:
            """Read an object as text (binary objects are reported by size only)."""
            if self._denied(bucket, key):
                return {"error": f"AccessDenied: not authorized to read s3://{bucket}/{key}"}
            path = (buckets / bucket / key).resolve()
            if buckets.resolve() not in path.parents or not path.is_file():
                return {"error": f"NoSuchKey: s3://{bucket}/{key}"}
            try:
                return {"key": key, **clip(path.read_text(), max_chars)}
            except UnicodeDecodeError:
                return {"key": key, "binary": True, "size": path.stat().st_size}

        return {f.__name__: f for f in (s3_list_buckets, s3_list_objects, s3_get_object)}
