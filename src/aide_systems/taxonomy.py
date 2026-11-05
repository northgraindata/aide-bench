"""Shared vocabulary for diagnoses. Agents pick from these categories; graders compare against them."""

CATEGORIES: dict[str, str] = {
    "data-loss": "Rows or values are silently dropped, filtered out or truncated.",
    "duplicate-data": "Rows are duplicated, for example by a retry or a join fan-out.",
    "schema-drift": "An upstream schema changed (renamed, retyped or removed column) and consumers broke.",
    "bad-input-data": "Source data is malformed or violates the contract the pipeline assumes.",
    "dependency-change": "A library, runtime or tool upgrade changed behavior.",
    "code-bug": "A defect in pipeline or transformation code.",
    "infrastructure": "Compute, network, storage or scheduler failure.",
    "permissions": "A credential or access policy blocks required access.",
    "no-issue": "The alert is a false alarm; the pipeline is healthy.",
    "unknown": "The available evidence does not establish a cause.",
}
VERDICTS = ("supported", "inconclusive")
