# Scope

Original implementation informed by the public README at https://github.com/krusemediallc/video-editor-agent (inspected 2026-10-10) and the user's existing caption/render workflow. No upstream source code is bundled.

| Capability | Implementation |
| --- | --- |
| Faceless long-form | Research → approved script → storyboard → narration/visuals → captions → render → QA |
| vidIQ | Connected research workflow; discover current tools and costs |
| ElevenLabs | Connected narration, receipts and job tracking; no embedded credentials |
| Canva | Connector editing; full-resolution export route must be verified |
| Pixabay | Sourcing/license/repetition workflow; no bundled API downloader |
| Whisper | Optional faster-whisper adapter using FFmpeg PCM decoding |
| Captions | Local SRT/VTT from measured word timestamps |
| Assembly | FFmpeg stills/clips, trims, framing, narration and burned-in captions |
| QA | Probe, full decode, black-frame/peak scan and sampled rendered frames |
| Review | Local HTML player, timestamped notes and JSON export |
| Resume | Artifact hashes, approval evidence, downstream invalidation and cost ledger |
| Music/SFX | Requires separate available mixing/generation tools and authorization |
| Gemini QA | Optional available service, not locally implemented |
| Advanced upstream lanes | Not ported: HyperFrames, hook batches, Arcads/OpenArt, CapCut layered drafts, here.now shared comments |

Don't claim a prompt alone renders videos in a host without execution. Ordinary Chat-only hosts can plan; actual assembly needs Work or a suitable execution environment. No paid generations are needed for installation tests.
