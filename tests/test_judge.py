import json

from aide_grade.judge import judge_facts
from aide_grade.schema import Fact

FACTS = [Fact(id="a", statement="A"), Fact(id="b", statement="B")]


def stub(answers):
    calls = iter(answers)

    def transport(payload, headers):
        return {"content": [{"text": json.dumps(next(calls))}]}

    return transport


def test_majority_vote(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    result = judge_facts("cause", FACTS, votes=3, transport=stub([{"a": True, "b": False}, {"a": True, "b": True}, {"a": False, "b": False}]))
    assert result == {"a": True, "b": False}


def test_judge_tolerates_prose_around_json(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")

    def transport(payload, headers):
        return {"content": [{"text": 'Sure: {"a": true, "b": true} done'}]}

    assert judge_facts("cause", FACTS, votes=1, transport=transport) == {"a": True, "b": True}
