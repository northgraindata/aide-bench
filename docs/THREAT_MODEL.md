# Threat model and known limits

This benchmark is meant to be hard to game by accident.
It is not designed to stop a determined adversary.
Know the limits before relying on a score.

## What is protected

- Ground truth, hidden tests and the reference solution live only in the verifier image.
  The verifier is a separate container (`verifier.environment_mode = "separate"`) that receives only the declared artifacts.
- The scenario files that build the world are deleted from the agent image after the build.
- Every file carries a canary string so that corpora can exclude the benchmark.

## What is not protected

- **Trace integrity.**
  The MCP server writes `/app/aide-out/trace.jsonl` inside the agent's container.
  An agent that also has a shell can edit the trace or the answer file, or read the world files directly.
  The `diagnose` instructions tell agents to use only the `aide` tools, and well-behaved agents do, but nothing enforces it.
  Treat results from agents with a general shell as less trustworthy than results from tool-only agents.
  Moving the MCP server and the trace out of the agent container is planned.
- **Contamination.**
  Public tasks and solutions can end up in training data.
  Only a held-out split with central verification addresses this, and 0.1.0 has none.
- **Emulation fidelity.**
  Flavors reproduce the surface of a product, not the product.
  An agent that learned real Airflow quirks may behave differently here.
  See `docs/FIDELITY.md`.
- **Task count.**
  Thirteen tasks is a small sample.
  A difference of one task is noise.
  Use repeated attempts and report intervals, not point estimates.
- **Pattern-based facts.**
  Regular expressions can credit a keyword without understanding and miss a valid paraphrase.
  Required evidence and categories gate the reward, so this mostly affects the non-gating `facts_recall`.

## Writing robust forbidden claims

A `forbidden_claims` pattern is checked against the whole root cause.
A correct answer often mentions the decoy in order to dismiss it, or quotes an injected instruction in order to report it.
Patterns such as `access denied` or `no issue was found` therefore punish good answers.
Prefer `forbidden_categories` and `forbidden_tools` for those cases.
Use `forbidden_claims` only for statements that cannot appear in a correct answer, and add a test with a correct answer that mentions the decoy.
