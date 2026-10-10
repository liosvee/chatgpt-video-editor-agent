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
