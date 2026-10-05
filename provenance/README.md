# Provenance and version boundaries

[Home](../README.md) · [Results](../results/README.md)

The original complete comparisons used `recorded_probe.py`, preserved byte for
byte here. Its SHA-256 is
`364dc6e0f465e0ab341e17acc837bd2fc05e40d7c0efa4e7f08a7ee7273c4234`.
It is an evidence artifact, not the recommended entry point. Its source hash
was taken at the end of each run; no start/end binding check was present.

Use `experiments/windows-execution/probe.py` for a new run. This public v2 adds
configurable shell paths, selected arms, missing-executable preflight, and a
start/end source-hash check. It retains the same eight fixture definitions.
That later runner must not be represented as the exact source of the older data.

## Development attempts, not hidden extra replications

- The first attempt used an invalid RPC enum. Commands did not run; those errors
  are an instrument defect, not shell failures.
- A four-arm, six-case development run exposed the Bash argument-conversion
  behavior. A later six-case run added the scoped-literal arm, but its source
  was edited during the run; it remains exploratory rather than qualification.
- The first expanded eight-case attempt stopped at an unhandled output-decoding
  error and did not produce a complete report. Capture-before-decoding and
  explicit parse-error handling repaired that seam.
- The recorded v1 harness then produced the selected baseline and candidate
  eight-case reports published here. They share the preserved source hash.

Only that final v1 source is included as a byte-bound archive. The earlier
development attempts are described for their limits, not presented as additional
independent evidence or claimed to have a complete published reproduction kit.

Recorded binary identities:

| Role | SHA-256 | Build boundary |
| --- | --- | --- |
| Baseline | `830a8d5d57cb86180514a1b6e458f0a67cafc12728e9a5a16d7a9a4c50f0a7e5` | Selected CodexPersonal 0.157.1 package, dev-small |
| Candidate | `a00bc24b489ca22a04985e1a59a3de77cd3e0cd76a1924646f54583280fa3b89` | Separately built 0.157.1 debug executable; not live Desktop activation |
| Public v2 validation | `543441200cc333639486dce09fa1f6926584fdf9ff2aeeb04c4e834c132cdde0` | Final 0.157.1 dev-small package from `af45068bd4299f481fbd77f60131b2b2d8d5641c`; not live Desktop activation |

The baseline package was built from source `1dcf0e4461ff08b111cca74c667449bda1033689`.
The patch base, `fff6b3c94035a3386b981dcaa63f8e3564943e78`, differs from it only
in two documentation files. The candidate production-code checkpoint was
`fd267c4110215f97f9523319a10a96a54cf0e779`; later commits add qualification and
test repairs. See the patch manifest for the exported final source boundary.
Binary hashes identify observations; they do not promise byte-reproducible builds.
The public v2 validation uses that final package, after formatting and packaging;
it is separate from the earlier debug candidate comparison and native test runs.

Research into interface choices included PowerShell, Git Bash, WSL, Nushell,
native process APIs, and Xonsh. Only the named local arms were executed in this
comparison. **Fae**, the project's named cloud-based LLM research and review
instance, supplied comparative research. **Coordinator**, its long-running local
Codex LLM instance, carried source work and local checks in collaboration with
**Kestrel**, the human project creator. These are project roles, not separate
human reviewers or model names. See [who is behind this](../README.md#who-is-behind-this).
This is AI-assisted engineering, with no claim of independent peer review.

Relevant outside sources:

- [Existing Git Bash dispatch report](https://github.com/openai/codex/issues/40328)
- [Type-based shell-resolution change](https://github.com/openai/codex/pull/39607)
- [Nushell: running external commands](https://www.nushell.sh/book/running_externals.html)
- [Nushell: stdout, stderr, and exit codes](https://www.nushell.sh/book/stdout_stderr_exit_codes.html)

The work does not claim first discovery of the shell regression or the idea of
argument vectors. Its contribution is the situated diagnosis, tested adaptation,
comparison material, and usable repair package.
