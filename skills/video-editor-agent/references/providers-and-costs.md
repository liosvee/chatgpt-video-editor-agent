# Provider and cost handling

Discover current tools and schemas and read each selected provider's skill. Never assume old MCP schemas or export capabilities still exist. Local scripts make no paid API calls.

Canva editing authentication may differ from browser sign-in. Check an export tool or full-resolution download before relying on Canva. A 1920×1080 design with a 596px preview is not a native 1920×1080 asset. Save stable IDs rather than ephemeral signed URLs.

ElevenLabs: verify voice, model, CONNECTOR input limit and estimate. Check billing workspace read-only if exposed; a personal subscription balance is not proof that a connected workspace uses it. Don't solicit keys in chat. Split before submitting; reuse audio; poll pending jobs instead of repeating creation.

vidIQ: record metric dates and costs. Research credits are not narration credits. No metric guarantees virality.

Pixabay: use genuine permitted downloads; record license evidence and provenance. Preserve missing-shot placeholders rather than fabricate access or licensing.

## Cost ledger

Use `project.py cost PROJECT --id OPERATION --provider PROVIDER --unit UNIT --estimated N --status estimated`. Update the SAME ID as the job progresses. Use separate IDs for distinct units; never total unlike credits.

Record ID, provider, unit, estimated/actual/refunded amounts, status, job ID, evidence and timestamp. Allowed statuses: estimated, submitted, succeeded, failed, refunded. Null actual/refund means unknown; failed does not mean free. Actual amounts need receipt evidence, not merely a successful job status.

Show expected whole-script credits and proposed retakes before generation; honor prior authorization for the exact operation. Do not silently buy top-ups, change billing workspaces or add subscriptions. Never convert credits into dollars without a verified applicable rate.

ChatGPT processing remains separate. This skill cannot guarantee zero ChatGPT charges or control host metering. For billing questions inspect the actual UI label/receipt and current official documentation. Do not assert that an estimated dollar figure was invoiced.

Private account IDs and receipts belong in project files, never committed skill source.
