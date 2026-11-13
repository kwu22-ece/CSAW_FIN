# Project Scribe handoff

Use the existing `DocumentAgent/openclaw-project-scribe` controller with a local configuration that observes the Phase 8 release worktree. Register this directory as a Git root. Set `git.sourceFiles` to the Phase 8 engineering, requirements, and Scribe handoff Markdown files. Keep controller state and reports outside the observed worktree.

Use `record-test` to log the saved provenance audit and, if desired, the clean baseline command. Example from the release worktree:

```text
node --no-warnings DocumentAgent/openclaw-project-scribe/scribe.mjs record-test --config ABSOLUTE_CONFIG --root ABSOLUTE_WORKTREE --session phase08-saved-evidence -- ABSOLUTE_PYTHON reproduce.py --evaluate-candidates
node --no-warnings DocumentAgent/openclaw-project-scribe/scribe.mjs preview --config ABSOLUTE_CONFIG
```

`preview` consumes local evidence and writes the controller's preview files. The engineering summary, requirements audit, and selected-revision manifests are the inputs for a final report. Check recorded command exits and tracked state before citing the run. Keep private transcript bodies out of Scribe source files.
