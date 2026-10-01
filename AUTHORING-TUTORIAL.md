# Record a reuse decision locally

This exercise uses public aggregates and invented endpoint definitions. It demonstrates the complete workflow without a server or recruited users. Run from the package folder with Python 3.10+.

1. Open `demo/index.html`. Choose Both conditions, one decision. Its structure is consistent, its endpoint is not identified, and the recorded action seeks information. Open the endpoint evidence to inspect both invented histories.
2. Run `python contracts.py examples/combined.json`. Compare the recomputed results with `demo/combined/evaluation.json`. Both mechanisms must be consistent to record a proceed action.
3. Copy `examples/endpoint-summary.json` to `work/edited.json`. Create `work` if necessary. Remove the `decision` object; change `id` to your exercise identifier. This is a new interpretation, not an authenticated clinical record.
4. Add `randomization`, `progression`, `death` and `last_contact` to `endpoint.available_components`. Keep the existing source summary fields. Edit `component_evidence` to state that this is a declared synthetic-component exercise. For actual reuse, bind each asserted available component to reviewed source evidence rather than copying this declaration.
5. Run `python contracts.py work/edited.json`. The conditions now support rederivation; the decision is unrecorded. No actual patient observations have been derived or clinically approved.
6. Record the scoped next step:

```powershell
python contracts.py work/edited.json --actor 'Tutorial participant' --action proceed_under_declared_conditions --reason 'Use the declared components with an established derivation package; obtain separate analysis review' --write work/recorded.json --export work/tutorial-crate
```

7. Open `work/tutorial-crate/report.html`. It shows the recorded action and reason. All three local parts are described in `ro-crate-metadata.json`.
8. Change the declared purpose in `work/recorded.json`, then replay it. The check can remain consistent while the previous decision becomes stale. A new decision requires the recording command again. A refreshed capture timestamp alone does not make unchanged semantic evidence stale.

For a structure exercise, start from `examples/sample.json`. The one-file-per-sample condition fails. Changing to `aliquot` or specifying a justified repeated-unit policy changes the condition; it does not establish that patients are independent. The evaluator never selects or deletes a file for you.
