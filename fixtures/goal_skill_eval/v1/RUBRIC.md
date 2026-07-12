# Goal Skill Behavior Evaluation Rubric v1

## Unit of Evaluation

Each observation represents one isolated runtime response to one manifest prompt.
The evaluator must record the decision before any generated artifact is inspected.
Artifacts, when expected, must be created under the observation file's directory
so the deterministic checker cannot inspect unrelated user files.

## Required Decision Fields

- `trigger`: whether `goal-preflight` should activate.
- `size`: `none`, `small`, `standard`, or `goal_grade`.
- `output_mode`: `none`, `chat`, `single_file`, or `directory`.
- `file_write`: whether the expected output writes a durable artifact.
- `review_required`: whether the response must retain a review gate.
- `reference_loads`: references actually loaded for the decision.

All six fields must exactly match the manifest expectation for a decision pass.
Trigger precision and recall are reported separately so over-triggering and
under-triggering remain visible even when aggregate decision accuracy is high.

## Artifact Checks

For a write-producing result, `artifact_paths` must be relative to the
observations JSON file. A `single_file` result must contain `GOAL.md` with a
`goal-contract` frontmatter type and a `## Contract` section. A `directory`
result must contain `CONTRACT.md`, `PLAN.md`, and `EVIDENCE.md` with their
respective frontmatter types and required sections. No-write fallbacks must not
claim any artifact paths.

## Regression Gate

Every recorded run must satisfy the manifest thresholds:

- trigger precision >= 0.90;
- trigger recall >= 0.90;
- exact six-field decision accuracy >= 0.85;
- all required artifacts valid.

The report also records unstable case IDs when repeated runs produce different
decisions. An evaluation is a usable semantic baseline only when its source is
`model_runtime`, the frozen Skill hash matches, all runs satisfy the gate, and
the observations cover every fixture exactly once per run.

## Non-Claims

Fixture/rubric validation, manually annotated data, or synthetic test data is
not a model-runtime baseline. Token metrics are reported only when the runtime
actually provides `token_count`; their absence is evidence of unavailable
instrumentation, not zero token usage.
