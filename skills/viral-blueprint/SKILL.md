---
name: viral-blueprint
description: >
  Find the most-viewed videos in the channel's niche with vidIQ, pick the top performers, and
  use their script, title, description, hashtags and tags as a BLUEPRINT for an original,
  improved next video — then hand the blueprint to the production lane. Use for "find viral
  videos in my niche and make a better version", "what's blowing up in my niche — copy the
  formula", "use the top video as a blueprint", "remake the best performer but better",
  "reverse-engineer the viral script/title/tags", or "next video based on what's working".
  Runs FIRST for every new video or episode, before any script is written. Skip only when
  revising or resuming an existing project (reuse its saved research) or when the user opts out.
  Never for re-uploading or closely paraphrasing someone else's video.
---

# viral-blueprint — learn from the niche's winners, ship something better

**This is the first stage of every new production.** Resumes and revisions reuse the project's
saved `viral/` files instead of re-running it; the user can opt out for a single video.

Eight steps: **search → select → check script → script blueprint → check title → title
blueprint → metadata blueprint → improved video**. vidIQ does the research through its MCP
connector; `scripts/blueprint.py` ranks, dissects and proves originality offline.
The production itself is the existing lane — this skill never renders on its own.

**Blueprint means structure, not words.** Keep what made the video work — hook shape, pacing,
beat order, devices, title pattern, metadata layout. Never reuse its sentences, title wording,
description text, thumbnail art or footage. `blueprint.py check` enforces this; an ERROR blocks
production. Improved means: a sharper hook, a payoff the original only teased, the channel's own
voice and verified quotes, tighter pacing, better-targeted keywords.

## Before you start

- This runs **inside** the [learning workflow](../video-editor-agent/evolution/WORKFLOW.md), not beside it.
  Run `learn.py begin` for the niche first; save every vidIQ response below into that run's
  evidence directory under the ignored `<project>/.evolution/` (or `<project>/viral/`), feed the
  picked videos into `refresh`, and bind the blueprint-driven script and packaging in `apply`.
  Resuming a project? Reuse its saved responses — do not repeat paid calls.
- Read the current project brief (and `../video-editor-agent/references/relationships-blueprint.md`
  for that channel): niche wording, own channel ID (to exclude), voice and format.
- **Cost.** Every vidIQ call used here costs 5 credits (outliers, search, get_videos_by_ids,
  transcript, score_title); `video_watch` / `watch_shortform_content` cost more — check the tool
  description. A typical run is ~12 calls ≈ 60 credits plus one watch job per pick. Tell the user
  the estimate before collecting, and check `vidiq_balance` first. Never auto-retry a charged call.

## 1 · Search the niche for viral videos

Long-form (any supported language) — outliers find videos beating their own channel's average:

```
vidiq_outliers  keyword="<niche>"  contentType="long"  language="en"  sort="viewCount"  limit=30
                minEngagementRate=0.02     # drops re-upload farms
```

Shorts: `contentType="short"` works for English. Add a raw-popularity pass so "most views" is not
only "most over-performing":

```
vidiq_youtube_search  query="<niche>"  type=["video"]  order="viewCount"  limit=25
                      videoDuration="short"|"medium"  publishedAfter=<window start>
```

Save each raw response as JSON (`viral/outliers.json`, `viral/search.json`). Then refresh stats,
descriptions and tags for every candidate ID in one call (≤ 50 IDs) and save that too:

```
vidiq_get_videos_by_ids  videoIds=[...]   →  viral/refresh.json
```

## 2 · Select the ones with the most views

```bash
python3 <skill>/scripts/blueprint.py select viral/outliers.json viral/search.json viral/refresh.json \
  --format long --niche "<niche>" --exclude-channel <own channel ID or @handle> \
  --max-age-days 365 --top 3 -o viral/selection.json
```

Ranks by view count after dropping the wrong format (Shorts ≤ 180 s), your own channel, uploads
younger than 3 days (views not settled) and records without a view count. One pick per channel by
default (`--per-channel`) so the blueprint is a pattern, not one creator's style. Narrow
`--max-age-days` when comparing raw views — a 3-year-old video wins on age alone. The full cohort
is saved, not just the winners. Show the user the top picks and let them choose (default: #1).

## 3 · Check the script

```
vidiq_video_transcript  videoId=<pick>  language="en"   →  viral/<id>.transcript.json
vidiq_video_watch (long) | vidiq_watch_shortform_content (Short)  →  save job ID, poll, save analysisText
```

The transcript is the spoken script, not the creator's written one; no captions → record the gap.
The watch analysis gives pacing, visuals and cuts. Then:

```bash
python3 <skill>/scripts/blueprint.py dissect viral/selection.json --video <pick> \
  --transcript viral/<id>.transcript.json -o viral/blueprint.json
```

`blueprint.md` shows runtime, words per minute, the hook window (first 30 s long / 3 s Short),
a 10-slice beat map with the devices in each slice (questions, open loops, lists, contrast turns,
CTAs), and the title and metadata anatomy.

## 4 · Use it as the blueprint for the next script

Write the next video's script in the channel voice (for Relationships Blueprint, follow
`../video-editor-agent/references/relationships-blueprint.md`), using the blueprint as a structural
brief, saved as `<project>/script.md`. `## ` chapter headings and `[bracketed]` visual notes are
ignored by the checker.

- Same job per beat, ~2–3 minute chapters for long-form, your own angle and examples. Treat
  attachment styles as patterns, not diagnoses; cite substantive research separately.
- Improve on it: pay off the hook sooner, cut beats the watch analysis flags as slow, close the
  loop the original left vague.
- Prove originality, then get the user's script approval as video-editor-agent requires:

```bash
python3 <skill>/scripts/blueprint.py check viral/blueprint.json --script <project>/script.md
```

## 5 · Check the title

`blueprint.md` → title anatomy: length, number, question, brackets, CAPS, "you", power words,
colon/dash split, and a slot pattern (`Why Strong Men {…}`). Pull 3–5 other picks' titles from
`selection.json` to see which patterns repeat across channels — a pattern shared by several
winners is stronger evidence than one title.

## 6 · Use it as the blueprint for the title

Draft 5+ titles that keep the winning **pattern** with new words and the channel's topic. Score
them (`vidiq_score_title type=long|short channelId=<own>`), optionally get more with
`vidiq_generate_titles`, keep the best under 70 chars, then:

```bash
python3 <skill>/scripts/blueprint.py check viral/blueprint.json --title "<chosen title>"
```

ERROR at ≥ 80 % similarity to the source title. The output lists which source patterns you kept.

## 7 · Description, hashtags and tags → improved versions

From `blueprint.md`: the above-the-fold line, links, timestamps, hashtags and tag set. Improve,
don't copy:

- Description: your own first lines with the main keyword, the channel's links. No sentences
  lifted from the source.
- Tags: keep the source's relevant descriptors, add keywords from `vidiq_keyword_research` for
  the niche and the channel's own terms; ≤ 500 characters.
- Hashtags: 3–5 relevant ones; the first three show above the title.

Then write `viral/upload.json` as `{"title": …, "description": …, "tags": […]}` (the same
text, for the checker) and run:

```bash
python3 <skill>/scripts/blueprint.py check viral/blueprint.json --script <project>/script.md \
  --upload viral/upload.json -o viral/check.json
```

## 8 · Make the improved video — hand off to the existing pipeline

With `check` at 0 errors and the script approved, hand off to **video-editor-agent**: storyboard
and cost estimate → ElevenLabs narration → Canva/stock visuals → measured captions → MP4 → QA
and review. Pass `viral/blueprint.md` and the watch analysis as the pacing/visual brief for the
storyboard. All its approval and cost checks apply; this skill never generates or renders.

After rendering, compare the actual pacing to the blueprint (beat starts vs the 10-slice map).
Re-run `check` if the script or packaging changes after review.

## Hand-off record

Keep in `<project>/viral/`: the saved vidIQ responses, `selection.json`, `blueprint.json/.md`,
`check.json`, the chosen title's vidIQ score, and a short `NOTES.md` listing what was kept from
the blueprint and what was deliberately improved. These are media-side project files — never
commit them to this repo. Generic lessons go through the learning workflow's sanitized knowledge.

## Honest limits

- "Most views" is within the sampled cohort, not the whole niche. Views are not CTR, retention
  or proof of *why* a video worked.
- A transcript is not the original script; missing captions stay a recorded gap.
- The originality check is lexical. It catches copied sentences, not a too-close idea — keep the
  angle your own.
