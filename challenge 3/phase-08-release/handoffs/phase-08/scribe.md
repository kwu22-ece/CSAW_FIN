# Existing Project Scribe handoff

The documentation owner is the existing `DocumentAgent/openclaw-project-scribe` controller. Phase 8 uses its `record-test` and `preview` interfaces with an isolated configuration observing the release worktree.

The current engineering and requirements reports, official-format submission brief, and selected-validation receipt are the ingestion inputs. The controller configuration and database remain in the project's ignored local state area outside the observed release worktree. Existing model configuration is a placeholder. Local preview and recorded execution events are the available documentation-agent outputs. Model-synthesized reporting and external publication remain unexecuted.

Record a selected checkpoint verification with the command below, using actual absolute paths:

```text
node --no-warnings DocumentAgent/openclaw-project-scribe/scribe.mjs record-test --config PRIVATE_CONFIG --root RELEASE_WORKTREE --session phase08-cycle03-selected --timeout 600 -- PYTHON reproduce.py --validate-selected --resume-selected ATTEMPT
node --no-warnings DocumentAgent/openclaw-project-scribe/scribe.mjs preview --config PRIVATE_CONFIG
```

The selected attempt contains the original execution receipts and logs. The Scribe checkpoint event verifies those artifacts and identifies its own command exit. Fresh execution and checkpoint verification are distinct evidence events.
