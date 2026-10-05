# Show and Tell draft — not posted

Suggested title: **Agent Toolbench: better hands for coding agents on Windows**

We started with “would Bash be easier for a coding agent than PowerShell?” and
found a more useful seam: sometimes the requested Bash wasn't being launched
at all. Codex could silently fall back to CMD.

That led to a small Windows execution lab:

- a candidate fix for shell discovery and explicit failure reporting;
- an additive `argv` route for ordinary executable/argument calls;
- a runnable comparison of direct execution, PowerShell, Git Bash, and Nushell;
- results, negative controls, regression tests, and the limits of what they show.

The fixed transport cases passed with direct arguments, Codex-style UTF-8
PowerShell, scoped-literal Bash, and Nushell. Plain PowerShell and default Git
Bash each exposed a different edge on our machine. This is not a claim that
one shell is universally best, or that we have measured better model reasoning.

The interesting direction is making the interface do more of the mechanical
work while retaining capable shells and the existing execution machinery.

[Agent Toolbench](https://github.com/puntastic/agent-toolbench)

You can read the findings without installing anything, reproduce the comparison,
or inspect the patches. Reproductions and counterexamples are welcome. The work
is AI-assisted, independently maintained, and currently Windows-specific.

---

Before posting: verify the public links and final status, and confirm the owner
wants the announcement sent. Repository publication is not an announcement.
