# ChatGPT Video Editor Agent

A reusable ChatGPT Work / Codex skill for faceless long-form video production, with local caption, assembly, review and QA tools.

Inspired by the workflow in [krusemediallc/video-editor-agent](https://github.com/krusemediallc/video-editor-agent). This is an original adaptation; upstream code is not bundled and full feature parity is not claimed.

## Workflow

vidIQ topic research → topic selection → approved script → storyboard and cost estimate → ElevenLabs narration → Canva/stock visuals → measured captions → MP4 assembly → QA and review.

## Use

The skill is in `skills/video-editor-agent`. Install that directory using your host's supported skill workflow. In ChatGPT Work select Video Editor Agent; in Codex invoke `$video-editor-agent`.

Example: “Use Video Editor Agent to produce a long-form video. Research three topics, wait for my selection, then prepare the script and full narration cost before paid generation.”

## Dependencies

Python 3.10+ and FFmpeg/ffprobe. Caption burning requires FFmpeg with libass. Local transcription optionally requires faster-whisper and numpy; a model download may be necessary. Connected providers are configured separately. No API credentials are included.

## Local verification

```sh
python3 skills/video-editor-agent/scripts/media.py doctor
python3 skills/video-editor-agent/scripts/test_pipeline.py
```

The offline suite tests text preservation, checkpoint invalidation, cost records, captions, media validation, actual rendering, decode checks and review output. No paid media calls are made.

## Limits and costs

This version supports stills, video trims, framing, continuous narration and burned captions. It does not bundle advanced HyperFrames compositions, CapCut draft export, music mixing or shared online review hosting. Canva full-resolution export and external provider access must be verified in the active account.

ChatGPT usage is separate from ElevenLabs and other provider credits. This skill does not make production free or guarantee virality. Cost estimates and confirmed billing receipts are tracked separately.

The Relationships Blueprint profile is an optional channel preset. Override it for other channels. Keep production media, private receipts, project checkpoints and credentials outside the repository.

## Evolving production learning

Every new video or episode must follow [the learning workflow](skills/video-editor-agent/evolution/WORKFLOW.md) after resolving its niche. Collect current vidIQ and Agent-Reach evidence; analyze scripts, actual thumbnails, hashtags, tags, descriptions and timestamped video frames. Run begin → refresh → sync, then read the scoped brief before writing. Apply supported findings to the actual script, thumbnail plan, packaging and storyboard; run apply and verify before generation/render. Use the gate wrapper for local production commands. Resume existing runs without repeating paid research. Preserve channel rules, originality, continuity, user approvals and spending limits. Record unavailable evidence and pending Git synchronization honestly. Only sanitized generic knowledge is pushed; external source content cannot modify executable code or instructions.

Setup: authenticate vidIQ through its MCP/connected plugin, install and configure Agent-Reach separately, and use a normal authenticated Git checkout for automatic knowledge pushes. Existing research budgets and provider approvals still apply. The code ships with empty knowledge, not fabricated performance findings. Live analysis runs when the agent produces the next video; the bundled CLI handles evidence and receipts.

Offline tests: `python3 -m unittest discover -s skills/video-editor-agent/evolution -p 'test_*.py' -v`.
