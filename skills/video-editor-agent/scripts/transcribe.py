#!/usr/bin/env python3
"""Optional local faster-whisper adapter. No paid API. Models may download on first use."""
import argparse
import difflib
import json
import re
import subprocess
from pathlib import Path


def normalize(text):
    return re.findall(r"\b[\w]+(?:['’][\w]+)*\b", text.lower().replace("’", "'"))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("audio")
    p.add_argument("--model", required=True, help="Existing model directory or a faster-whisper model name")
    p.add_argument("--language", default="en")
    p.add_argument("--script", help="Approved narration; produces discrepancy report without changing words/times")
    p.add_argument("--out", required=True)
    a = p.parse_args()
    out = Path(a.out)
    if out.exists():
        p.exit(1, "Output exists; choose a new version.\n")
    try:
        import numpy as np
        from faster_whisper import WhisperModel
    except ImportError:
        p.exit(1, "Optional dependencies missing: install faster-whisper and numpy before using this adapter.\n")
    decoded = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", a.audio,
                              "-f", "f32le", "-ac", "1", "-ar", "16000", "-"], capture_output=True)
    if decoded.returncode:
        p.exit(1, decoded.stderr.decode(errors="replace"))
    signal = np.frombuffer(decoded.stdout, dtype=np.float32).copy()
    if not len(signal):
        p.exit(1, "No audio samples decoded.\n")
    model = WhisperModel(a.model, device="cpu", compute_type="int8", cpu_threads=2)
    segments, info = model.transcribe(signal, language=a.language, word_timestamps=True, beam_size=5)
    words, segments_out = [], []
    for segment in segments:
        segments_out.append({"start": segment.start, "end": segment.end, "text": segment.text})
        words.extend({"word": w.word.strip(), "start": w.start, "end": w.end, "probability": w.probability}
                     for w in (segment.words or []))
    result = {"model": a.model, "language": info.language, "duration": len(signal)/16000,
              "words": words, "segments": segments_out, "human_verified": False}
    if a.script:
        expected = normalize(Path(a.script).read_text(encoding="utf-8"))
        observed = normalize(" ".join(w["word"] for w in words))
        differences = []
        for tag, i, j, x, y in difflib.SequenceMatcher(None, expected, observed, autojunk=False).get_opcodes():
            if tag != "equal":
                differences.append({"operation": tag, "script_word_range": [i,j],
                                    "transcript_word_range": [x,y],
                                    "expected": expected[i:j], "observed": observed[x:y]})
        result["script_comparison"] = {"expected_words": len(expected), "recognized_words": len(observed),
                                       "differences": differences, "requires_review": bool(differences)}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(out.resolve()), "words": len(words), "duration": result["duration"],
                      "human_verified": False}))


if __name__ == "__main__":
    main()
