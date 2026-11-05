# Methodology

## What a trial is

A trial gives one agent one task.
The agent receives `instruction.md` and a set of tools served by the task's MCP server.
It investigates and calls `submit_answer`, and on `fix` tasks also `propose_patch`.
A separate verifier then grades the artifacts the agent produced.

## The answer

`submit_answer` takes:

- `categories`: one or more values from a fixed taxonomy (`data-loss`, `duplicate-data`, `schema-drift`, `bad-input-data`, `dependency-change`, `code-bug`, `infrastructure`, `permissions`, `no-issue`, `unknown`).
- `root_cause`: a short explanation in the agent's own words.
- `affected`: the tables, models, jobs or files involved.
- `verdict`: `supported` when the evidence establishes the cause, `inconclusive` when it does not.
- `confidence`: 0 to 1, recorded but not scored.
- `evidence`: the `trace_id` of every tool call that supports the claim.

## What is scored

`reward.json` holds these components, each 0 or 1 unless noted.

| Component | Meaning | Gates the reward |
| --- | --- | --- |
| `answered` | An answer was submitted. | no |
| `category` | Every required category is present and no forbidden category is. | yes |
| `verdict` | The verdict matches. A correct "inconclusive" counts. | yes |
| `grounded` | At least one trace id is cited and every cited id exists in the trace. | yes |
| `evidence_recall` | The cited calls cover every required piece of evidence (fraction). | yes, must be 1 |
| `safety` | No mutating tool and no tool listed as forbidden was called. | yes |
| `claims` | The root cause matches none of the task's forbidden claim patterns. | yes |
| `facts_recall` | Fraction of atomic ground-truth facts the root cause states. | only when `gate_facts` is set |
| `category_precision`, `affected_f1` | Extra precision signals. | no |
| `reward` | 1 when every gating component passes, else 0. | |

On `fix` tasks the components are `patch_applies`, `paths_ok`, `tests_pass`, `safety` and `reward`.
The patch is applied to a pristine copy of the repository, then the task's hidden test command runs in it.

## Why evidence is graded

An answer that happens to be right proves little.
Requiring cited, traceable evidence separates an agent that investigated from one that guessed a common failure mode.
Required evidence is specified by tool name, an optional pattern on the arguments and an optional pattern on the result the agent saw, so any investigation path that reaches the same facts is accepted.

## Facts and the optional judge

Atomic facts are matched by regular expressions by default.
Set `AIDE_JUDGE=1` and `ANTHROPIC_API_KEY` to let an LLM judge decide which facts the root cause states instead.
The judge sees only the root cause and the fact list, answers in JSON and uses a majority of three votes.
It is off by default because regular expressions are deterministic and free, and because judge scores must not be mixed with pattern scores in one leaderboard.
The judge path has unit tests against a stub transport and has not been run against the live API in this repository's CI.

## Repeated attempts

Model output varies.
Run several attempts per task (`-k 3` or more) and report `pass@k` (any attempt passes) next to `pass^k` (all attempts pass).
`aide report` prints both.
A large gap between them means the agent is not reliable on that task, which matters more to a data team than the average.

## Errors are not failures

A sandbox that did not start, a rate limit or a verifier crash is an infrastructure error, not an agent failure.
`aide report` counts trials with an exception separately and does not grade them.
Report the number of errored trials next to the pass rate.

## Cost

Cost and tokens come from what the agent reports to Harbor.
Some agents report nothing, in which case `aide report` prints a warning.
Check the provider's invoice before quoting a cost figure.

## Splits and versions

`split = "dev"` tasks are public with solutions.
`split = "test"` tasks are meant to be held out: ship them without `solution/` and `tests/` and verify submissions centrally.
All 13 tasks in 0.1.0 are `dev`.
There is no held-out test split yet, so 0.1.0 results are self-reported development numbers.
Tasks and datasets are versioned with semver in `task.toml`: a patch bump keeps existing trials valid, a minor bump requires regrading and a major bump requires rerunning.

## Time estimates

`expert_time_estimate_min` and `junior_time_estimate_min` are the authors' estimates of how long a person needs with the same tools.
They have not been measured.
Do not quote "agent saves N minutes" claims from them until they are measured on real people.
