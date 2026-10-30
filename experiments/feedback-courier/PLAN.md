# Feedback courier: make a legitimate report easy to carry

Build a small explicit operator for a caller-authorised, observed action-review
denial. This is product feedback, not a safety bypass, a diagnosis that every
denial is wrong, or a support-case API. The caller supplies a deliberately
sanitised account; the helper never reads transcripts, private prompts, auth
files, browser cookies or reviewer reasoning to construct it.

## Current boundary

Official Codex app-server documentation exposes feedback/upload. A selected
cloud runtime0.166.0-alpha.1 exports it in its default schema. The separately
inspected older0.157.1 source supports no-thread/no-logs/no-extra-files requests,
but process/account metadata may still be sent. Schema equality does not prove
implementation equality or server-side association/retention. The default here
is preparation only. Live submission needs an independently authorised caller
who has accepted that residual metadata boundary; the flag is not authority.

There is no inspected Guardian-specific event subscription on that cloud host.
This helper can be called after a genuine visible denial; it is not an automatic
all-events detector. Generic cancellation, a validation error, an auth outage,
pending approval and a denied review are distinct. Never recursively report a
failure of this reporter as a fresh Guardian incident.

## Implementation slice

One Python stdlib module and synthetic tests. Explicit input JSON, explicit
private ledger path, and an operator-selected Codex executable. No global
install, new daemon, scheduler, account, credential or approval setting.

- Accept an allowlisted, bounded incident object with stable logical incident
  key, reporter designation, observed timestamp, actual product/runtime,
  affected operation, an authored redacted observation and a short explanation
  of the already-given authority or expected result. Mark source/attribution
  limits. Only explicit review/Guardian denial is eligible for this operator;
  generic cancellation is not silently promoted. IDs are optional when absent.
- Reject unknown input fields, control/header injection and obvious token/key
  patterns. This is a limited guard, not comprehensive automatic redaction.
  Keep source text as data, never interpolate it into a shell or executable.
- Build a concise complaint and exact feedback/upload params: classification
  safety_check, reason only, includeLogs false; omit threadId, extraLogFiles and
  tags. No option here enables attachments or inserts another runtime's thread.
- Default command prepares/inspects without spawning a process or network call.
  An explicit send action also requires a metadata-acceptance flag and current
  caller authority. Use a fresh normal-home Codex app-server stdio process;
  never override CODEX_HOME, feedback configuration, analytics or permissions,
  attach to a running daemon, or issue model/thread/tool requests. Bind the
  public initialise/initialised/feedback-upload sequence and own only that
  disposable process. Bound runtime, output and shutdown; no unsupervised child.
- Record intent durably before dispatch. Stable incident key plus canonical
  content digest prevents duplicates and rejects changed content under the
  same key. An accepted response is feedback HTTP acceptance, not ticket creation
  or human review. Unknown post-dispatch outcome must not auto-retry; retain it
  for inspection. Explicit pre-dispatch failure is different. No retry loop,
  fabricated receipt or synthetic external test report.
- Preserve a ready-to-send plain text fallback. Gmail/support delivery remains
  a separate supported caller operation, not a hidden generic HTTP/SMTP adapter.
  No message or draft is sent by preparation.

Actual reports and local ledger data stay outside this public repository. All
test cases are invented and marked synthetic. The repository remains an
independent engineering project, not an OpenAI product or endorsement.

## Evidence to seek

Test strict parsing, literal Unicode/quotes, minimal outgoing shape, duplicates,
conflicting keys, process-initialisation/config refusals, bounded output/time,
accepted/unknown outcomes, interrupted persistence and absence of retries.
Mock/process-fixture contacts are not a live report. Do not provoke a denial,
send fake complaints or change settings to force a success. Source/live/delivery
boundaries and a real next decision belong in the final hand.
