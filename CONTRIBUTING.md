# Help improve the evidence

Questions, useful failures, and small fixes are welcome. Start with the
[findings](docs/findings.md) or the [run guide](experiments/windows-execution/README.md).
You do not need to reproduce everything before pointing out one problem.

For a useful result report, include:

- the question you were testing;
- OS and executable versions, selected arms, and relevant flags;
- the specific case and expected/observed result;
- whether the harness completed and whether output was capped;
- a reviewed result excerpt or a link to a sanitized report.

Keep a program failure, a launch failure, a harness defect, and an unexpected
comparison result distinct where the evidence permits it. A different result
can be useful rather than something to hide.

Please review files before sharing them. Local reports contain executable paths,
commands, and potentially diagnostic details. `scripts/export_report.py`
creates a reduced public view; it is not a universal secret detector.
Avoid credentials, private repositories, chat transcripts, and unrelated files.

For changes, state the problem and the test that would detect it. Preserve
existing result records; add a new version or correction instead of rewriting
an older observation into a cleaner story. The portable data tests run with:

```console
python -m unittest discover -s tests -v
python scripts/check_results.py
```

Runner/source binding is checked too. When changing the runner, retain the
measured version with its evidence or produce a new run and describe the new
boundary. Editing an old digest to make a test green is not a new observation.

This repository carries no promise of a response time or of merging every
suggestion. You can use or fork the work under its license without waiting for
project approval. A reproduction or a concise question is enough to participate.
