# Results you can inspect

[Home](../README.md) · [Interpretation](../docs/findings.md)

`baseline.json` and `candidate.json` are reduced views of the two complete
48-observation runs from 5 October 2026. The original byte captures and full
reports are retained locally by the project, outside this public repository.
Public projections omit local commands,
startup descriptors, and free-form diagnostic text; they do not change recorded
checks or pass/fail values. Each projection carries the original report's hash.

`qualification.json` records the separate native-source test runs and their
limits. These are not model-performance evaluations.

`harness-v2-validation.json` checks the public runner's later usability changes
against the same eight fixtures. Its 48 observations reproduce the same recorded
pass/fail pattern, with matching start/end source hashes. It is a runner check,
not a third independent model trial or a clean timing comparison. This check
used the final packaged candidate; its binary identity is listed in
[provenance](../provenance/README.md).

Run the portable checks without installing Codex or any extra Python package:

```console
python scripts/check_results.py
python -m unittest discover -s tests -v
```

The checker verifies structure and internal consistency, not that a reported
execution happened or that an interface is generally better. Running the
[experiment](../experiments/windows-execution/README.md) provides a separate
observation on your setup.

The fixed expected outputs are visible in the harness. Large repetitive streams
are represented here by byte counts and SHA-256 hashes; no full chat logs,
credentials, or compiled executables are included.
