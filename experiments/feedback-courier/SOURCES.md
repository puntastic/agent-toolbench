# Reporting routes and disclosure boundaries

Checked30 October2026 UTC. These are dated source observations, not proof a
particular account or future build exposes the same route.

- [Codex app-server](https://learn.chatgpt.com/docs/app-server) documents
  `feedback/upload` as a programmatic feedback operation. It is not described
  as creating a support ticket or accepting an appeal.
- [Developer commands](https://learn.chatgpt.com/docs/developer-commands?surface=cli),
  [troubleshooting](https://learn.chatgpt.com/docs/reference/troubleshooting) and
  [configuration](https://learn.chatgpt.com/docs/config-file/config-advanced)
  describe interactive feedback/diagnostics and the feedback configuration.
  Existing disablement is not something this helper changes.
- [Contact Support](https://help.openai.com/en/articles/6614161-how-can-i-contact-support)
  currently directs users through the Help Centre chat. It asks for a clear
  description, reproduction, timestamp/environment and actual error/request IDs
  when available, with sensitive data removed. No support-ticket automation
  API was established by this inspection.
- [A resolved Help Centre incident](https://status.openai.com/incidents/01M3Q4HMNP8SZ27DTZKW6F5BJ4)
  named `support@openai.com` as a fallback while chat was unavailable. A genuine
  dated address is not proof of current automated intake or guaranteed response.
- [Data-use guidance](https://help.openai.com/en/articles/5722486-how-your-data-is-used-to-improve-model-performance)
  distinguishes feedback with an associated conversation from Support
  correspondence. A short report body does not bound every disclosure made by
  its transport or settle provider-side retention/association.
- [Support conduct](https://help.openai.com/en/articles/10082939-communicating-with-openai-support)
  addresses repeated unwelcome conduct. This does not establish a numerical
  feedback quota. Coalescing retries and respecting actual limits are design
  choices here, not invented provider policy.

## Version-bound source inspection

A clean local Codex-derived checkout at
`fff6b3c94035a3386b981dcaa63f8e3564943e78`, package0.157.1, was inspected without
executing its uploader. Relevant paths under `codex-rs/` were:

- `app-server-protocol/src/protocol/v2/feedback.rs` and `protocol/common.rs`;
- `app-server/src/request_processors/feedback_processor.rs`;
- `feedback/src/lib.rs`, `feedback/src/upload.rs` and `feedback/src/guardian.rs`;
- `ext/guardian-reviewer/src/feedback.rs` and `core/src/guardian/feedback.rs`.

In that source, an initialised caller and enabled feedback configuration are
required. Classification is required; reason, threadId, includeLogs,
extraLogFiles and tags are optional. `includeLogs:false` suppresses the normal
automatic attachments. Supplying extraLogFiles is a separate path, so this
helper never exposes it. Omitting threadId skips rollout-derived metadata and
uses a synthetic no-active-thread identifier; it does not infer an active
conversation. Cached account IDs and process-wide diagnostic/correlation tags
can still be added. There is no public parameter here that strips all metadata.

Success returns a thread identifier and optional prompt hash, not a ticket or
review decision. There is no exposed caller idempotency key/status query; losing
the response after dispatch must not trigger a blind resend. Internal Guardian
analytics/capture is a different lane from user complaint submission, and may
contain reviewer context that this helper neither seeks nor attaches.

Separately, a cloud operator's actual Codex0.166.0-alpha.1 default and experimental
protocol exports both included `feedback/upload` with the same named fields.
This is direct schema exposure, not a matching implementation audit, live
method permission, successful upload or privacy validation. Its reported
available events did not include Guardian/approval-denied notifications. These
observations motivate an explicit caller, not an asserted universal hook.

No source code or private incident material from that environment is vendored
here. The client is independently authored against the public protocol.
