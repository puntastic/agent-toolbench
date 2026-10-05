# Inspect or try the changes

[Home](../README.md) · [Findings](../docs/findings.md)

The exported patches target the recorded **CodexPersonal** source base in
`manifest.json`, not an unspecified current upstream checkout. They are
experimental source changes, not an installer or an automatic Desktop update.
Use a separate checkout and keep your working installation available.

| Patch | Purpose |
| --- | --- |
| `01-native-argv-and-shell-resolution.patch` | Add the model-facing direct-argument route, repair Windows Bash discovery, return explicit shell-resolution errors, and carry the relevant tests/snapshots |
| `02-mailbox-history-mode-tests.patch` | Ancillary repair: exercise mailbox steering under both legacy and thread-owned history modes; no production behavior change |

Read `manifest.json` for the exact base, final source, file hashes, and check
status. For a fresh trial, run this from the Agent Toolbench repository root
in PowerShell. It creates a **sibling** checkout, not a replacement installation:

```powershell
$patches = (Resolve-Path .\patches).Path
$trial = Join-Path .. 'codex-toolbench-trial'
git clone --filter=blob:none https://github.com/puntastic/CodexPersonal.git $trial
git -C $trial switch -c toolbench-trial fff6b3c94035a3386b981dcaa63f8e3564943e78
git -C $trial apply --check "$patches\01-native-argv-and-shell-resolution.patch" "$patches\02-mailbox-history-mode-tests.patch"
```

After the applicability check succeeds, apply the selected changes:

```powershell
git -C $trial apply "$patches\01-native-argv-and-shell-resolution.patch" "$patches\02-mailbox-history-mode-tests.patch"
git -C $trial diff --stat
```

The patches touch disjoint paths and can be selected independently. Then follow
the target repository's `AGENTS.md`, `docs/install.md`, and Windows developer-lane
guide for the build you intend. Compilation can be substantial; reading the
results or running the transport harness does not require rebuilding Codex.
No commit, installation, permission change, or replacement of a running Codex
occurs merely by downloading or applying these patches.

## Qualification notes

The core suite needs separately built helper executables, including
`test_stdio_server`, `codex-code-mode-host`, and `codex`. A missing helper is not
an interface result. On Windows, some sandbox integration tests provision local
users and firewall rules; those tests were excluded from this experiment rather
than run as ordinary workstation checks.

The recorded checks cover the mechanisms named in the report. Full workspace,
cross-host, live-model, and post-activation Desktop behavior are separate evidence
surfaces. The project did not enable Guardian or change its permission defaults.

## Rollback

For an uncommitted experimental patch, preserve your own work and use a separate
checkout you can discard. For committed integration, revert the task-owned
commits. If you independently install a build, retain the previous package and
use your host's supported selection/rollback process. This repository does not
manage your installation or erase runtime data.
