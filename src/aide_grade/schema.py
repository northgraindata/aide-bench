"""Ground truth schema. Lives in the verifier only; the agent never sees it."""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aide_systems.taxonomy import CATEGORIES, VERDICTS


class EvidenceRequirement(BaseModel):
    """A tool call the agent must have made *and cited* to support its claim."""

    model_config = ConfigDict(extra="forbid")
    tool: str = Field(description="Regex that must fully match the tool name.")
    args_regex: str | None = Field(default=None, description="Regex searched in the JSON-encoded arguments.")
    result_regex: str | None = Field(default=None, description="Regex searched in the tool result the agent saw.")


class Fact(BaseModel):
    """An atomic statement the root cause should contain. Matched by regex, or by a judge when enabled."""

    model_config = ConfigDict(extra="forbid")
    id: str
    statement: str
    patterns: list[str] = Field(default_factory=list, description="Any match (case-insensitive) counts as stated.")


class FixSpec(BaseModel):
    """Hidden tests for tasks of the fix track."""

    model_config = ConfigDict(extra="forbid")
    test_command: str = Field(description="Run in the patched repository copy; exit code 0 means pass.")
    allowed_paths: list[str] = Field(default_factory=list, description="Path prefixes a patch may touch. Empty means any.")
    max_changed_lines: int | None = None


class GroundTruth(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track: str = "diagnose"
    categories: list[str] = Field(default_factory=list, description="Categories a correct answer must include.")
    forbidden_categories: list[str] = Field(default_factory=list)
    verdict: str = "supported"
    affected: list[str] = Field(default_factory=list)
    required_evidence: list[EvidenceRequirement] = Field(default_factory=list)
    forbidden_tools: list[str] = Field(default_factory=list, description="Tools that must not be called (safety).")
    forbidden_claims: list[str] = Field(default_factory=list, description="Regexes that must not appear in the root cause.")
    facts: list[Fact] = Field(default_factory=list)
    gate_facts: bool = Field(default=False, description="Require every fact for a passing reward (multi-cause tasks).")
    fix: FixSpec | None = None

    @field_validator("categories", "forbidden_categories")
    @classmethod
    def _known(cls, values: list[str]) -> list[str]:
        bad = [v for v in values if v not in CATEGORIES]
        if bad:
            raise ValueError(f"unknown categories {bad}; known: {sorted(CATEGORIES)}")
        return values

    @field_validator("verdict")
    @classmethod
    def _verdict(cls, value: str) -> str:
        if value not in VERDICTS:
            raise ValueError(f"verdict must be one of {VERDICTS}")
        return value

    @model_validator(mode="after")
    def _consistent(self) -> "GroundTruth":
        if self.track == "fix" and self.fix is None:
            raise ValueError("fix track requires a `fix` section")
        if self.track == "diagnose" and not self.categories:
            raise ValueError("diagnose track requires at least one category")
        if set(self.categories) & set(self.forbidden_categories):
            raise ValueError("a category cannot be both required and forbidden")
        return self


def load_ground_truth(path: Path) -> GroundTruth:
    return GroundTruth.model_validate(yaml.safe_load(path.read_text()))
