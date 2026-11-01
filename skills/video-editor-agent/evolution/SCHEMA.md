# Evidence and application schema (version 1)

Use `begin`'s generated `run_id`, `scope` and fresh timestamp. All source paths
are project-relative, resolve inside the project, and refer to saved local
files (maximum 20 MB each). Store raw evidence inside `.evolution/`; never stage
it. The engine hashes source files so later changes invalidate verification.

`discovery`: `status` is `ok`, `partial` or `unavailable`; non-ok requires a
`reason`. Provide `method` (queries, coverage and limitations), `metric` (one of
`viewCount`, `vph`, `outlierScore`), `age_days: [minimum, maximum]`, `top_n` and
`sources: [{"file": ".evolution/runs/RUN/raw/search.json"}]`. The publication-age
window must fit within one year. Save the actual metadata response and point at
each video row with a JSON pointer, e.g. `/videos/0`. Do not synthesize provider
metrics. An unavailable run has zero videos and zero new lessons.

Each `videos` entry (maximum 100 candidates) has:

```json
{
  "id": "YOUTUBE_ID1",
  "channel_id": "ACTUAL_CHANNEL_ID",
  "scope": {"niche": "ACTIVE NICHE", "language": "en", "market": "US", "format": "long"},
  "scope_basis": "Describe actual content verification and why this audience/niche matches",
  "content_verified": true,
  "observed_at": "REPLACE WITH CURRENT ISO TIMESTAMP WITH TIMEZONE",
  "duration_seconds": 600,
  "metadata": {"file": ".evolution/runs/RUN/raw/metadata.json", "pointer": "/videos/0"},
  "metric_value": 123,
  "facets": {
    "script": {"status": "observed", "method": "transcript", "observation": "Original analytical notes",
      "source": {"file": ".evolution/runs/RUN/raw/transcript.json"}, "timestamps": [2, 45]},
    "thumbnail": {"status": "observed", "method": "image_inspection", "observation": "Actual visual notes",
      "source": {"file": ".evolution/runs/RUN/raw/thumbnail-notes.md"},
      "image_file": ".evolution/runs/RUN/raw/thumbnail.jpg"},
    "hashtags": {"status": "observed", "method": "metadata", "observation": "Relevant hashtags in description; or observed none",
      "source": {"file": ".evolution/runs/RUN/raw/metadata.json", "pointer": "/videos/0"}},
    "tags": {"status": "unavailable", "reason": "Provider returned null tags"},
    "description": {"status": "observed", "method": "metadata", "observation": "Describe structure and relevance",
      "source": {"file": ".evolution/runs/RUN/raw/metadata.json", "pointer": "/videos/0"}},
    "frames": {"status": "observed", "method": "video_analysis", "observation": "Timestamped visual evidence",
      "source": {"file": ".evolution/runs/RUN/raw/watch-result.md"}, "timestamps": [1, 30, 120]}
  }
}
```

This is structural documentation, **not usable evidence**. Replace every value
with observations. `metric_value` must equal the chosen raw field on the saved
metadata row; `id`, `channelId` and `publishedAt` must be present there. `tags`
requires a known list; hashtags/description require a known description string.
Keep tags `null` unavailable. A known empty list or description is observable.
For `frames.method = frame_inspection`, also provide `frame_files` with paths
to the permitted samples actually inspected. `script` alternatively accepts
`video_analysis`. Never use transcript/metadata as visual evidence.

`lessons`: a list of `{id, facet, observation, application, video_ids}`. IDs use
3–64 lowercase letters, digits, hyphens or underscores, starting with a letter.
The facet is one of the six keys. Use concise original English summaries
(maximum 600 characters each); URLs belong only in generated source citations.
Keep a stable ID for a recurring pattern. `video_ids` cites unique members of
the engine's selected top-N with that facet observed. Three independent
channel IDs promote the lesson; fewer keep it in `hypotheses`.

`retire`: optional list of `{id, reason, video_ids}` to retire an existing active
rule using relevant observed counterevidence in this sample. Do not renew and
retire the same ID in one run. The Git history preserves earlier revisions.

The application input is a separate project file:

```json
{
  "run_id": "CURRENT_RUN_ID",
  "production_inputs": ["speech.plan.json", "render.json"],
  "facets": {
    "script": {
      "artifact": "script.md",
      "decisions": [{"rule_id": "clear-payoff", "decision": "applied",
        "reason": "How this original script uses the abstract finding",
        "excerpt": "An exact excerpt that exists in script.md"}]
    },
    "thumbnail": {"artifact": "thumbnail-plan.md", "decisions": [], "fallback_reason": "No active thumbnail rule; use channel visual identity"},
    "hashtags": {"artifact": "packaging.md", "decisions": [], "fallback_reason": "No active hashtag rule; use a few relevant descriptors"},
    "tags": {"artifact": "packaging.md", "decisions": [], "fallback_reason": "No active tag rule; use relevant search phrases"},
    "description": {"artifact": "packaging.md", "decisions": [], "fallback_reason": "No active description rule; accurately explain the payoff"},
    "frames": {"artifact": "storyboard.json", "decisions": [], "fallback_reason": "No active visual rule; follow the original storyboard"}
  }
}
```

Address **all** current active rules for their facet, even carried-over ones.
Use `not_applicable` with a reason when necessary; it needs no excerpt. Empty
decisions are valid only when that facet has no active rules. Actual production
artifacts must exist and be nonempty UTF-8 text. Several facets can bind the
same packaging file. For native Japanese/Korean scripts use `script.ja.txt` or
`script.ko.txt`; for drama, script and frames may bind the same shot list.

`production_inputs` lists existing local plans/manifests actually consumed by
the next native generation/render command. Include only files already prepared;
add the measured timeline later and re-apply. The engine hashes these files too
and rejects production commands using an unbound input in an active run.
