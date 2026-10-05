# Run the Windows execution comparison

[Home](../../README.md) · [Findings](../../docs/findings.md) · [Results](../../results/README.md)

## Before running

This experiment is Windows-specific. It needs Python 3.11+, a native Codex
executable, and PowerShell 7. The full six-arm comparison also needs Git for
Windows and Nushell. Obtain those tools separately; this repository does not
install or download them for you. The recorded setup used Python 3.12,
PowerShell 7.6.6, Git Bash 5.3.15, Nushell 0.116.1, and Codex 0.157.1.

Use the actual `codex.exe`, not an npm `.cmd` wrapper. The runner starts its own
unauthenticated app-server with fresh Codex and SQLite homes, remote control
disabled, and no model inference requests. It neither resumes your chats nor
selects a replacement Desktop binary.

The native RPC commands run **without a sandbox** to isolate transport behavior.
They execute the supplied local software and the fixed fixtures in `probe.py`.
The Windows case reads its own process, the EventLog service, and the output
directory's path/ACL metadata; it emits booleans, not those underlying details.
Review the code and use a test account/VM if that better fits your circumstances.
No machine-level sandbox accounts or firewall rules are provisioned.

## First run: one interface

From the repository root in PowerShell, replace the executable path:

```powershell
python experiments/windows-execution/probe.py `
  --codex 'C:\path\to\codex.exe' `
  --arms direct `
  --output out/direct-run
```

PowerShell is still needed for the Windows-native inspection case. Its default
path is `C:\Program Files\PowerShell\7\pwsh.exe`; use `--powershell` for another
installation. Git Bash similarly accepts `--bash` for a nonstandard location.

## Full comparison

```powershell
python experiments/windows-execution/probe.py `
  --codex 'C:\path\to\codex.exe' `
  --nu 'C:\path\to\nu.exe' `
  --output out/full-run
```

Each output directory must be new. Pick another name to rerun; existing results
are preserved. A completed full run writes 48 observations and separate stdout
and stderr byte files. The original two negative controls may fail a check;
process exit zero means the runner completed, **not** that every arm passed.

```powershell
python scripts/check_results.py out/full-run/report.json
```

The checker summarizes evidence; it does not make a benefit or safety judgment.
If initialization or RPC preflight fails, fix that instrumentation problem
before interpreting shell results. Newer Codex versions are not automatically
covered by the recorded 0.157.1 contract.

## Share a smaller reviewed result

```powershell
python scripts/export_report.py out/full-run/report.json `
  --output out/public-run.json --label my-windows-run
```

This removes launch commands, the startup descriptor, and free-form diagnostics
from the public view. It retains checks, exit status, output lengths/hashes,
elapsed times, and source hashes. Review the exported file before sharing;
the exporter is not a universal anonymizer. Keep the local originals if you
want to investigate a discrepancy later.

The harness tests native `command/exec` transport. It does not require the
`argv` patch and does not by itself test the model-facing shell-selection fix.
Those changes have their own [source tests and application route](../../patches/README.md).
