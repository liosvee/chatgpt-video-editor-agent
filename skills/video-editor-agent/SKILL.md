---
name: video-editor-agent
description: Produce and revise faceless long-form YouTube videos or assemble supplied footage in ChatGPT Work, from vidIQ topic research and approved scripts through ElevenLabs narration, Canva and stock visuals, measured captions, MP4 rendering, QA and review. Use for video production, resuming an approved video, scene timing, captioning and final assembly. Exclude standalone thumbnails and unrelated voice agents.
---

# Video Editor Agent

Run production using connected capabilities and local media tools. This is an original ChatGPT adaptation informed by [krusemediallc/video-editor-agent](https://github.com/krusemediallc/video-editor-agent), not a vendored copy or feature-parity claim. Read [capabilities.md](references/capabilities.md) for supported lanes. Actual rendering requires Work with execution tools.

## Start or resume

1. Identify faceless production, supplied-footage assembly, or revision. Preserve earlier topic choices, scripts, approvals, voice, costs and assets. Never restart a paid stage because conversation context is incomplete.
2. Resolve named projects through Library when appropriate and materialize their checkpoint with the Library skill. Keep media outside this skill. For a new project run `python3 <skill>/scripts/project.py init <project> --title '<title>'`. For an existing project run `project.py status <project>` and inspect changed/missing artifacts.
3. Read the current brief. For this user's Relationships Blueprint channel use [relationships-blueprint.md](references/relationships-blueprint.md) unless superseded; do not apply those defaults to other channels.
4. Run `python3 <skill>/scripts/media.py doctor`. Discover current connector capabilities; read the relevant provider skills. Record available access and tested export routes in the project's capabilities.json.
5. Test full-resolution visual retrieval early. Canva editing access does not establish export access. Prefer a connected export tool; use permitted browser fallback when necessary, obeying secure sign-in. If only thumbnails are available, disclose the blocker before spending on visual-dependent production. Offer user export or an explicit alternate visual method, not silent substitution.
6. Report completed stages, the next step and concrete blockers. Never imply planned work is complete or background work continues after the turn.

## Research and script

- Use vidIQ's topic/keyword workflow when requested. Check credits; return multiple original topics with evidence of demand, competition, comparable outliers and channel fit. Label unavailable metrics. Never promise virality or invent search volume.
- Let the user choose when the workflow calls for topic selection. Carry previous selections forward.
- Divide long-form outlines into approximately 2–3 minute chapters. Count narration only. Preserve the exact approved script. Do not stretch 1,230 words to meet a 10–12 minute target without agreement.
- Obtain script approval once per changed script. Cite substantive research separately from spoken text. Treat attachment styles as patterns, not diagnoses.
- Create a storyboard with shot IDs, chapters, narration cues, provisional timings, visuals, overlay copy, sources and sound. Long scene groups require internal cuts where useful; don't hold a text card for a minute simply because it spans that paragraph.
- Checkpoint script/storyboard with `project.py record`. Add `--approved --evidence '<actual user approval/date>'` only after genuine approval. Re-recording changed inputs invalidates downstream stages.

## Costs and narration

- Read [providers-and-costs.md](references/providers-and-costs.md) before paid operations. Separate ChatGPT usage, ElevenLabs credits, Canva/stock and other generators. Never promise this skill avoids ChatGPT usage charges.
- A reported personal ElevenLabs balance does not prove which workspace the plugin bills. Resolve active workspace, voice, model and rate when exposed; otherwise mark billing linkage and dollar cost unverified. Never request API secrets in chat.
- Split below the actual CONNECTOR text limit; a model's API limit may differ. Use `project.py split SCRIPT --max-chars N --out DIR --rate R`, with N/R verified from the current provider. Show whole-script estimate plus proposed retakes before generation. Work within existing spending authorization.
- Use Frederick Surrey for this user's Relationships Blueprint projects, subject to current voice lookup. Reuse approved auditions and audio. Poll existing jobs; never resubmit pending jobs. Save IDs, receipts, downloaded outputs and refund status. Estimates are not charges.
- Verify decoding, duration, missing/repeated words, seams and pronunciation. Correct only affected sections, asking for extra spending approval only when needed.

## Visuals, captions and timing

- Use Canva's connector for editable cards and full-resolution exports for final assembly. Verify actual pixel dimensions, not design metadata or an upscaled output's dimensions.
- Source stock through the user's selected provider, such as Pixabay. Record URL, creator, license evidence, download date, filename and permitted use. Never invent licenses, strip watermarks or bypass access controls. Flag exact replays and visually similar shots. Keep illustrative characters consistent.
- Prefer local Whisper when available to avoid a separate paid transcription call; [cli.md](references/cli.md) describes the optional adapter. Correct against the approved script and audit discrepancies. Do not fabricate timestamps for missing words.
- Build SRT/VTT from measured word times with `media.py captions WORDS.json --out DIR`. Schema: `{"words":[{"word":"Hello","start":0.2,"end":0.7}]}`. Inspect grouping/readability. Script-length timing estimates are not final captions.
- Build timeline.json using [timeline-format.md](references/timeline-format.md), including internal shot changes and provenance. Derive chapter markers from actual cues. [timeline.example.json](assets/timeline.example.json) is only a schema example.

## Render, verify and revise

- Run `media.py validate TIMELINE.json`; correct missing assets, low resolution, trim ranges and timing. Render a NEW filename with `media.py render TIMELINE.json --out OUTPUT.mp4`. Use `--allow-preview` only for labelled draft review. Never overwrite a delivered render.
- The bundled renderer supports stills, video trims, contain/cover framing, continuous narration and burned-in SRT. It does not implement all upstream motion graphics, music mixing, CapCut or multi-camera lanes; see capabilities.md.
- Run `media.py qa OUTPUT.mp4 --out QA_DIR --expected-duration SECONDS`. Inspect extracted frames from the actual MP4; listen to chapter starts, seams, names and ending. Full decoding is not a full editorial watch/listen. The report leaves caption accuracy and editorial review unverified. Investigate black-frame flags; intentional black shots are not necessarily faults.
- Generate `media.py review OUTPUT.mp4 --out review.html`. Notes remain in the local browser and export to JSON; don't imply remote persistence or a live public URL. Save render, captions, timing, QA, ledger and checkpoint through Library.
- For revisions, inspect the exact timestamp, capture before/after evidence, edit affected shots, retain earlier versions and update checkpoints. Do not regenerate narration for purely visual revisions.
- Deliver links plus measured duration, dimensions, checks performed and limitations. Label drafts honestly. Publish only when explicitly authorized for that video/account.

## Persistence

Read [cli.md](references/cli.md) for commands. Never commit media, secrets, billing records or production checkpoints into this skill. Save production artifacts through Library or the user's designated repository. Save skill changes through the managed Git repository. Carry approvals across turns without inventing them. If blocked, finish independent authorized work, preserve a resumable checkpoint and give one specific next action.
