# Local commands

Python 3.10+ and FFmpeg/ffprobe are required. Core tools otherwise use the Python standard library. Paths below are placeholders: use the actual skill directory and a separate production directory. No command contacts paid providers.

## Checkpoint and cost

```bash
python3 <skill>/scripts/media.py doctor
python3 <skill>/scripts/project.py init <project> --title "Approved video title"
python3 <skill>/scripts/project.py record <project> script <project>/script.txt --approved --evidence "Actual user message/date"
python3 <skill>/scripts/project.py status <project>
python3 <skill>/scripts/project.py split <project>/script.txt --max-chars 4500 --rate 1 --out <project>/narration-parts
python3 <skill>/scripts/project.py cost <project> --id narration-01 --provider ElevenLabs --unit elevenlabs_credit --estimated 2000 --status estimated
```

4500 and 1 above are illustrative, not verified limits or rates. Splitting preserves ALL source characters, including separators, and never splits a word. Keep headings out of script.txt. Re-running to an existing split directory refuses overwrite. Unknown rate produces null estimated credits.

Update the same cost ID after a real provider receipt using --actual, --job-id and --evidence. Never insert illustrative amounts as receipts. Different services/units require separate IDs. Failed jobs retain unknown actual/refund unless evidenced.

## Transcription and captions

The optional adapter requires faster-whisper and numpy. Inspect environment first; install only when needed from a reputable package registry. A named model may require a first-use download; an existing model path avoids it.

```bash
python3 <skill>/scripts/transcribe.py <project>/audio.mp3 --model <existing-model-directory> --script <project>/script.txt --out <project>/words.json
python3 <skill>/scripts/media.py captions <project>/words.json --out <project>/captions-v1
```

The adapter decodes with FFmpeg rather than PyAV to avoid media-decoder compatibility issues. It reports differences against the script without inventing alignments. Review low-confidence/missing/repeated words. The caption tool intentionally refuses invalid/overlapping word times instead of silently assigning new ones.

## Assembly and QA

```bash
python3 <skill>/scripts/media.py validate <project>/timeline.json
python3 <skill>/scripts/media.py render <project>/timeline.json --out <project>/video-v1.mp4
python3 <skill>/scripts/media.py qa <project>/video-v1.mp4 --out <project>/qa-v1 --expected-duration 600
python3 <skill>/scripts/media.py review <project>/video-v1.mp4 --out <project>/review-v1.html
```

Use the measured expected duration, not the illustrative 600. Export original full-resolution images from Canva. A draft with --allow-preview has a burned label and warning report. The renderer stages small sequential clips to keep memory bounded, then muxes audio/captions once. It preserves older outputs and writes a sibling .render.json receipt.

QA outputs include full probe metadata, a complete decode scan, black intervals, sample peak dBFS and seven frame samples. This is technical QA, not full visual or spoken-content verification. Still cards naturally freeze; no universal freeze detector is treated as a failure. The report does not mark publication-ready automatically.

The HTML review references the adjacent media by a relative path. Keep the HTML and video together when downloading or serving. Notes persist only in that browser when local storage is available; export JSON to send feedback. No public review hosting is installed automatically.

## Offline regression test

```bash
python3 <skill>/scripts/test_pipeline.py
```

Tests exercise exact text preservation, stale approval detection, unknown versus confirmed costs, caption boundaries, undersized visuals, invalid clip trims, real rendering/decoding, overwrite protection and local review output. Synthetic media is built in a temporary directory; no narration generation, paid calls or source media is committed.
