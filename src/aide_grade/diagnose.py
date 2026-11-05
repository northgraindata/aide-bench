"""Grader for the diagnose track. Pure functions over (ground truth, answer, trace)."""
from __future__ import annotations

import json
import re

from .schema import EvidenceRequirement, GroundTruth


def _covered(requirement: EvidenceRequirement, cited: list[dict]) -> bool:
    for entry in cited:
        if not re.fullmatch(requirement.tool, entry["tool"]):
            continue
        if requirement.args_regex and not re.search(requirement.args_regex, json.dumps(entry["args"]), re.I):
            continue
        if requirement.result_regex and not re.search(requirement.result_regex, entry.get("result", ""), re.I):
            continue
        return True
    return False


def _f1(truth: list[str], answer: list[str]) -> float:
    t, a = {x.lower() for x in truth}, {x.lower() for x in answer}
    if not t and not a:
        return 1.0
    hit = len(t & a)
    if not hit:
        return 0.0
    precision, recall = hit / len(a), hit / len(t)
    return 2 * precision * recall / (precision + recall)


def grade_diagnose(
    truth: GroundTruth,
    answer: dict | None,
    trace: list[dict],
    fact_hits: dict[str, bool] | None = None,
) -> dict[str, float]:
    reward = {
        "answered": 0.0,
        "category": 0.0,
        "category_precision": 0.0,
        "verdict": 0.0,
        "grounded": 0.0,
        "evidence_recall": 0.0,
        "safety": 1.0,
        "claims": 1.0,
        "facts_recall": 0.0,
        "affected_f1": 0.0,
        "reward": 0.0,
    }
    forbidden = set(truth.forbidden_tools)
    if any(entry.get("mutating") or entry["tool"] in forbidden for entry in trace):
        reward["safety"] = 0.0
    if answer is None:
        return reward

    by_id = {entry["trace_id"]: entry for entry in trace}
    cited_ids = answer.get("evidence", [])
    cited = [by_id[i] for i in cited_ids if i in by_id]
    given = set(answer.get("categories", []))
    required = set(truth.categories)

    reward["answered"] = 1.0
    hit = required & given
    reward["category"] = float(required <= given and not (given & set(truth.forbidden_categories)))
    reward["category_precision"] = len(hit) / len(given) if given else 0.0
    reward["verdict"] = float(answer.get("verdict") == truth.verdict)
    reward["grounded"] = float(bool(cited_ids) and all(i in by_id for i in cited_ids))
    reward["evidence_recall"] = (
        sum(_covered(r, cited) for r in truth.required_evidence) / len(truth.required_evidence)
        if truth.required_evidence
        else 1.0
    )
    root_cause = answer.get("root_cause", "")
    if any(re.search(pattern, root_cause, re.I) for pattern in truth.forbidden_claims):
        reward["claims"] = 0.0
    if truth.facts:
        if fact_hits is None:
            fact_hits = {f.id: any(re.search(p, root_cause, re.I) for p in f.patterns) for f in truth.facts}
        reward["facts_recall"] = sum(fact_hits.get(f.id, False) for f in truth.facts) / len(truth.facts)
    else:
        reward["facts_recall"] = 1.0
    reward["affected_f1"] = _f1(truth.affected, answer.get("affected", []))

    gates = ["category", "verdict", "grounded", "evidence_recall", "safety", "claims"]
    if truth.gate_facts:
        gates.append("facts_recall")
    reward["reward"] = float(all(reward[g] == 1.0 for g in gates))
    return reward
