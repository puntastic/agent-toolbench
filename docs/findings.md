# Windows execution: what we found

[Home](../README.md) · [Run it](../experiments/windows-execution/README.md) ·
[Evidence](../results/README.md) · [Changes](../patches/README.md)

## Why look below the command text?

A command can fail because the agent wrote it incorrectly, because the runner
selected the wrong interpreter, because a shell changed an argument, or because
the program itself failed. Those are different repair targets.

On the observed Codex setup, explicitly requesting Git Bash produced CMD's
“printf is not recognized” error. Launching the installed Bash executable
directly worked. An existing [community report](https://github.com/openai/codex/issues/40328)
describes the same class of failure. We reproduced it on the project's
Codex 0.157.1 fork and inspected the responsible path.

The model-supplied shell path selected a shell **type**; the host then searched
for an executable. Windows Bash discovery missed standard Git for Windows
locations and could silently fall back to CMD. The candidate keeps type-based
discovery, adds Windows Git locations, and makes an unavailable explicit request
fail clearly. It does not trust arbitrary model-supplied shell paths.

## Two evidence paths, kept separate

| Path | What it tests |
| --- | --- |
| Fixed fixtures → native `command/exec` RPC → executable | Argument, output, exit-status, and data-view mechanics across interfaces |
| Mock model tool calls → patched `exec_command` → existing runtime → executable | The model-facing `argv` addition, Bash selection, input-mode rejection, permission rejection, and interactive-session behavior |

The comparison harness launches each shell explicitly. It deliberately bypasses
the broken model-facing shell selector, so it can compare transport without
confusing that defect with Bash's language behavior. Mock model calls are
deterministic integration tests, not live model reasoning trials.

RPC means a program asking another process to perform an operation. Here those
requests go to an isolated **local** Codex process over stdin/stdout; they are
not cloud model requests. We first isolate the mechanics so a runner defect
cannot masquerade as a model's language mistake.

## Eight transport cases

1. Arguments containing spaces, empty strings, quotes, backslashes, shell-like
   characters, Unicode, and a leading slash.
2. Valid JSON on stdout with a deliberate nonzero exit and separate stderr.
3. Non-JSON stdout with a successful exit.
4. Binary bytes on both output streams.
5. Concurrent 256 KiB stdout and stderr.
6. Stdin delivery and EOF.
7. Reading, filtering, sorting, and projecting a small JSON table.
8. Windows-native process, service, path, and ACL inspection.

### Recorded results

The two published eight-case runs produced the same pass/fail pattern:

| Interface | Baseline binary | Candidate binary | Observed edge |
| --- | ---: | ---: | --- |
| Direct executable/arguments | 8/8 | 8/8 | None in these cases |
| PowerShell, plain invocation | 7/8 | 7/8 | Unicode JSON view did not survive the output encoding |
| PowerShell with Codex's existing UTF-8 setup | 8/8 | 8/8 | None in these cases |
| Git Bash, default conversion | 7/8 | 7/8 | `/not-a-path` changed when passed to a native program |
| Git Bash, scoped literal-argument setting | 8/8 | 8/8 | None in these cases |
| Nushell | 8/8 | 8/8 | None in these cases |

The plain PowerShell result is **not** a newly discovered live Codex defect:
Codex already applies the UTF-8 setup represented by the next row. The Bash
literal arm sets `MSYS2_ARG_CONV_EXCL='*'` only for that invocation; no global
shell setting was changed. Different machines or future versions can change
these observations.

Timings are retained in the data, but are not a speed ranking. These were
single fixed-order runs on a machine doing other build work, and the baseline
and candidate used different build profiles. There is no statistical
performance claim.

## The proposed interface change

Most calls to Git, ripgrep, Python, or Node need an executable and arguments,
not a shell program. The additive `argv` field carries those arguments directly.
`cmd` remains available for scripts, pipelines, builtins, and shell-dependent
environment setup. A request containing both is rejected.

The implementation uses the existing process, approval, hook, output, and
session machinery. Direct arguments bypass shell snapshots and shell-specific
rewriting. Existing executable-identity checks remain in the path.

Current boundaries are explicit: direct `argv` is unavailable in zsh-fork mode
and with credential brokerage; those callers retain `cmd`. Windows batch files
need an explicit interpreter. Adding `argv` is not a general safety guarantee
for arbitrary commands.

## Qualification and repairs

The broad core run was useful even when it was not green. Its first pass had
204 failures, many caused by missing separately built helper programs. After
building the prerequisites and excluding six machine-provisioning sandbox
cases, 4,135 of 4,151 cases passed. The remaining failures were fourteen
expected tool-schema snapshots and two pre-existing mailbox test assertions.

The snapshot updates were reviewed. All **346** focused shell, execution, and
scenario checks then passed, including six model-facing tool-loop cases.
The mailbox assertions reproduced unchanged on the starting commit. They
expected thread-owned ordering metadata from a legacy-mode fixture; the repair
tests both modes explicitly. All **40** related checks passed. No production
messaging behavior or live Guardian setting was changed by that test repair.

These counts are separate runs with overlapping coverage. They must not be
added into a larger independent sample. The whole workspace suite and an
end-to-end broad rerun after every repair are not claimed here.

Earlier harness attempts also exposed an invalid RPC enum and an unhandled
decode error. They were corrected and are not counted as complete interface
comparisons. Raw stream capture now precedes decoding. The public runner adds
explicit executable paths, arm selection, preflight checks, and start/end
source-hash comparison. [Provenance and version boundaries](../provenance/README.md)
keep those generations distinct.

## What remains open

- Does the extra `argv` affordance reduce real model mistakes or work/context
  cost over ordinary tasks? No live-model comparison has established that yet.
- What happens on other Windows versions, locales, installations, and hosts?
- Does Nushell's structured-data vocabulary repay its learning/context cost
  in larger workflows? One small data-view case cannot settle that.
- Which changes survive contact with normal use after activation? Source tests
  and an isolated binary probe do not prove Desktop tool exposure.
- How should direct execution expand into the currently unsupported execution
  modes without changing their existing contracts?

The practical direction is additive: remove an unnecessary parsing layer for
ordinary program calls while keeping capable shells available where they help.
