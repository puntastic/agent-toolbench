# Checks and limits

Checked 30 October 2026 UTC on Windows, Python 3.14.6. This is a tested
implementation candidate, not an activated reporting service or a successful
live feedback submission.

## Local checks

- Focused suite: 32 tests, 28 passed and four explicitly skipped POSIX-only
  fixtures.
- Full repository suite: 49 tests, 45 passed and those same four skipped.
- Independent receiving review found no material remaining issue in the final
  lock, interruption, receipt and complaint-wording changes; it independently
  reran the focused suite with the same outcome.
- Process fixtures use invented incidents and synthetic peers. They exercise
  actual local pipes, bounded output/time and owned-process cleanup without
  running Codex or sending an external report.

The source and test hashes exercised by these local checks were:

| File | SHA-256 |
| --- | --- |
| `feedback_courier.py` | `145268cc3afcd6570e23b52a20391446429a320597fece43e6a08f25c86da93d` |
| `tests/test_feedback_courier.py` | `e57a5eddfbf9c36b1afdb65df30fbe960aa2579a24f895e4cedf9ac0dcbbf243` |

The test path is repository-relative; the module is beside this document.
Documentation edits after these checks do not change the two tested files.

## What the checks cover

Strict incident parsing; literal Unicode; limited secret/control rejection;
minimal outgoing fields; explicit metadata acceptance; content/key conflicts;
durable intent before dispatch; duplicate and unknown-outcome holds; distinct
incident pacing; persistence failure; real fake-peer initialization, timeout and
output-flood handling; accepted receipts; process-constructor interruption
windows; and no implicit retries or network calls during preparation.

Receipt fields follow the exported string contract rather than imposing a
particular hash/ID spelling. Unknown response extensions are ignored rather
than persisted or interpreted. A zero exit code can mean deferred or prepared,
not sent.

## Remaining evidence boundaries

The Windows fixtures substitute POSIX privacy, directory-fsync and locking
where needed. They do not prove real POSIX modes, lock validation, process-death
lock release or signal/process-group cleanup. Four separate fixtures are
present for a POSIX host, including a synthetic lock-owner death test. Hosted
check status should be read from the exact source revision, not assumed from
this local record.

No actual Codex app-server, upload, support email/draft or account change was
performed. Public documentation, inspected older source and a newer cloud
runtime's exported schema are different evidence; none establishes live route
permission, server-side association/retention or support response.

Activation still needs an accepted disclosure route, actual caller authority,
and a verified persistent private ledger location for the CLI sender. No
durable filesystem location was established in the inspected cloud setting.
Exposed mail draft/send/read methods are a possible separate route, not a
tested durable queue or exactly-once delivery mechanism. This candidate does
not silently choose that route or enable automatic reporting.
