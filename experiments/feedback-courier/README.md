# Feedback courier

**Give a blocked piece of work a clear report and a traceable outcome.**

This small operator prepares a report about an explicitly observed Guardian or
action-review denial. An independently authorised caller can also use Codex's
documented `feedback/upload` operation. Preparation is the default: it makes no
process, network call or local record unless a ledger was explicitly selected.

This is **product feedback**, not a help-desk ticket, an appeal decision, or a
mechanism for bypassing the original denial. It does not detect every blocked
action automatically. A caller needs an actual visible event and a configured
reporting agreement; a generic cancellation is not enough to identify its cause.

## First decide what may leave

The report text is deliberately authored and redacted. The courier does not
collect a prompt, transcript, credentials, HAR, screenshot or reviewer reasoning
to fill it. Its outgoing request uses `includeLogs:false` and omits `threadId`,
`extraLogFiles` and `tags`.

That is **not a promise of metadata-free feedback**. Inspected Codex source can
add account and process metadata even when logs are disabled. The protocol has
no public switch to suppress all of it, and schema inspection cannot establish
server-side association or retention. Before enabling sends, the person owning
the account should accept that boundary or choose another supported route.
Acceptance can cover a bounded standing workflow; it need not be asked again
for every report inside it.

Official ChatGPT guidance also distinguishes response feedback, which can make
an associated conversation available for model improvement, from Support
correspondence. Do not equate a short message with a small disclosure merely
because its attachments are empty. The [source and route notes](SOURCES.md)
keep these distinctions beside the implementation.

For a sanitised message-body route without diagnostic attachments, the prepared
`fallback_text` can be used by a separately authorised mail/support operator.
Email still carries sender and transport metadata, and Support correspondence
is not categorically exempt from model-improvement settings. Compare those
real disclosure paths once when choosing the route. This program does not send
email, create a draft, configure an account or invent a support endpoint.

## Prepare one real incident

Supply UTF-8 JSON through a named file or stdin. Use one stable logical incident
key; retries of that same event should not become a pile of complaints.
Describe the operation and why a different outcome was expected without copying
the private work itself. Preserve uncertainty in `source_limits`.

The following is an **invented example, not a report to submit**:

```json
{
  "incident_key": "example-review-denial-01",
  "kind": "review_denial",
  "reporter": "example-agent",
  "observed_at": "2026-10-31T10:00:00+10:00",
  "product": "Example Codex environment",
  "runtime": "Version observed by the operator",
  "operation": "Create a requested project pull request",
  "observation": "The visible action review denied the request as unauthorised.",
  "authority_or_expectation": "The user had directly requested this operation in the current task.",
  "source_limits": "Synthetic documentation example; no real denial or submission."
}
```

`kind` is `guardian_denial` or `review_denial`; it is the caller's source-bound
classification, not a verdict the schema proves. Optional `review_id` and
`call_id` carry identifiers actually available. `reported_impact` can preserve
reported manual work or attention cost without inventing it or collecting
unrelated personal information. Do not invent missing IDs or
quietly relabel an authentication error, pending approval, validation error or
unattributed cancellation. Never recursively report this reporter's own failure.

Text fields are bounded single-line descriptions. The helper rejects unknown or
duplicate fields, control/header injection and some obvious secret-like strings.
Those checks are not a comprehensive redaction service: inspect the selected
meaning before it leaves.

From the repository root:

```console
python experiments/feedback-courier/feedback_courier.py prepare --input incident.json
```

Omitting `prepare` has the same preparation-only default. `--input -` reads
stdin as data; do not interpolate source text into executable shell code.
Output includes the exact minimal `feedback_params`, a digest and plain
`fallback_text`. A prepared report has not been sent.

## Keep sending state beside the work

An explicit ledger makes duplicate and interrupted attempts inspectable. Keep
it outside this public repository, in an existing absolute owner-only POSIX
directory. The helper verifies that boundary rather than treating a pathname
as privacy. Ledger-backed preparation and sending currently require POSIX;
portable stdout-only preparation also works on Windows. Windows ACL privacy is
not inferred from `chmod` bits and there is no assertion flag to force it.

```console
python experiments/feedback-courier/feedback_courier.py prepare --input incident.json --ledger /absolute/private-directory/reports.json
```

The same key with different content is a conflict, not permission to replace an
earlier account. A different genuinely observed incident gets its own key.
The caller still owns this distinction; changing a key cannot turn a retry into
a new event.

The adjacent owner-private `.lock` file is a persistent coordination inode.
POSIX releases its `flock` when the owning process exits or dies; the file is
not a stale-lock marker. Do not delete it to force progress. An interrupted
incident's durable dispatch intent remains held even after that lock releases.

Distinct events can also arrive in bursts. A configured sender needs pacing as
well as deduplication: preserve each distinct prepared report, send serially
within the chosen cadence and respect actual recipient limits. A deferred item
is **not sent**, not discarded or secretly counted as delivered. This is a
one-time workflow choice within the standing grant, not another approval chore
for every incident. The helper does not start a background queue-draining loop.
The initial default spacing is 600 seconds between durable dispatch intents,
configurable with `--min-interval-seconds`: a project starting policy, not an
OpenAI quota or a measured safe rate.

This first ledger is bounded to 256 incidents and 4 MiB. At its limit it refuses
further records rather than erasing earlier evidence. Keep that maintenance
boundary visible; a missing or newly recreated ledger does not prove that an
earlier report was never sent.

## Send only through an accepted route

Once the disclosure and standing authority are settled, an operator can select
the actual trusted Codex executable and send:

```console
python experiments/feedback-courier/feedback_courier.py send --input incident.json --ledger /absolute/private-directory/reports.json --codex /absolute/path/to/codex --accept-runtime-metadata
```

The flag records the caller's acknowledgement; it does not create permission.
This starts one fresh app-server stdio process using its normal home/settings,
initialises the connection and submits the single feedback request. It does not
attach to a running daemon, alter `CODEX_HOME`, override feedback configuration,
request a model/thread/tool run, or enable analytics. Normal Codex startup may
have its own state/cache effects; this is not a side-effect-free executable.
A denied or unavailable route is not permission to switch around it.

The courier records intent before dispatch, bounds process lifetime/output and
owns shutdown of that disposable child only. There is no unattended retry loop.
An accepted result means feedback transport acceptance—not a support case,
human review, correction, response promise or proof the original denial was
wrong. If the response is lost after dispatch, keep the attempt unconfirmed;
it may already have arrived. Inspect that state before any further action.

Inspect `status`, `dispatched_this_call` and any receipt, not just the process
exit code. Successful preparation, an already-accepted duplicate and a paced
`deferred` result can all exit zero without sending a new report.

## Fit it to an agent without inventing an event source

An agent may call the configured operator after a visible qualifying denial,
keeping the actual report and outcome out of unrelated work. This is a possible
turn-level workflow, not an all-events subscription. If a platform hides a
decision or ends the turn before exposing it, this helper cannot reconstruct
it by confidence. A platform-provided event route would be a separate capability.

Once configured, ordinary reporting should not transfer the same navigation
and retelling work back to the person. Keep the original task parked or moving
through its legitimate options; lodging feedback does not complete that task
and does not grant the denied action. Stop repeated reporting of one incident,
respect recipient limits, and never invent success to close the loop.

## Evidence and status

This is an experimental, explicitly operated candidate. The task's tests use
invented incidents and controlled process fixtures; they must not send fake
complaints. Actual runtime exposure, an accepted live submission, server-side
handling, reliable recruitment and usefulness are separate evidence.

See [the checks and limits](RESULTS.md), [the build plan](PLAN.md) for the current scope and [source notes](SOURCES.md)
for what the inspected surfaces establish. Nothing in these files enables
automatic reporting, changes approval policy or installs a recurring worker.
