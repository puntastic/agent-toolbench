# Agent Toolbench

**Better hands for coding agents.** Small, runnable experiments on the boundary
between an agent's decision and the tools that carry it out.

The first experiment examines Windows command execution: direct argument lists,
PowerShell, Git Bash, and Nushell. It includes a Codex repair candidate, the
comparison harness, selected results, and the things the evidence does **not**
yet establish.

## Pick your path

| I want to… | Start here |
| --- | --- |
| Understand what we found | [Findings](docs/findings.md) — no installation required |
| Run the comparison | [Reproduce the experiment](experiments/windows-execution/README.md) |
| Try or inspect the changes | [Patches and their boundaries](patches/README.md) |
| Check the evidence | [Results and provenance](results/README.md) |

## The short version

- An explicit request for Git Bash could silently run through CMD instead.
  The candidate repairs discovery and returns an error when a requested shell
  cannot be found.
- Ordinary program calls can use a separate `argv` list, avoiding an extra
  layer of shell parsing. Scripts and pipelines remain available through `cmd`.
- The fixed transport cases passed with direct execution, Codex-style UTF-8
  PowerShell, scoped-literal Git Bash, and Nushell. Plain PowerShell and Git
  Bash each exposed a different edge on the tested machine.
- This is **mechanical and integration evidence**, not a demonstration that a
  model writes better Bash, that one shell is universally superior, or that
  the changes improve every coding task.

**Status:** experimental engineering work on one Windows setup. Read the
[limits](docs/findings.md#what-remains-open) before treating it as a recommendation
for your environment. Applying patches, running the harness, and installing a
modified Codex are separate choices; nothing here installs itself.

## A small example

```json
{"argv": ["git", "status", "--short"]}
```

`argv` means the executable followed by its separate arguments. The example
requires the patched model-facing tool; it is not a promise that your current
Codex accepts that field. Existing `cmd` calls keep their script behavior.

## Make the result more useful

A reproduction on another Windows setup, a counterexample, or a clear report
of what was hard to follow is welcome. [How to contribute](CONTRIBUTING.md)
describes a small useful report; no full workstation dump is needed.

## Who is behind this?

This work grew from **Song of the System**, Kestrel's human-led project exploring
how tools, skills and working methods can make LLMs more useful and dependable.

- **Kestrel** is the human project creator, shaping its goals, design choices
  and adoption decisions.
- **Fae** is a named cloud-based LLM instance supporting research and review.
  Fae supplied the comparative research for this experiment.
- **Coordinator** is the project's long-running local Codex LLM instance.
  Coordinator implemented, tested and packaged this work in collaboration with
  Kestrel.

Fae and Coordinator are project designations for AI instances, not separate human
contributors or model names. This is AI-assisted engineering, not independent
peer review. The project is independently maintained, not an OpenAI product or
endorsement. See [provenance](provenance/README.md) and [licensing](NOTICE).
