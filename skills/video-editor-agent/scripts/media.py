#!/usr/bin/env python3
"""Local media tools; no external service calls or automatic dependency installation."""
import argparse
import html
import json
import math
import re
import shutil
import subprocess
import tempfile
import textwrap
from pathlib import Path
from urllib.parse import quote


def run(args, cwd=None):
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if result.returncode:
        raise ValueError(f"{args[0]} failed: {result.stderr[-2500:]}")
    return result


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def probe(path):
    return json.loads(run(["ffprobe", "-v", "error", "-show_format", "-show_streams",
                           "-of", "json", str(path)]).stdout)


def duration(info):
    return float(info.get("format", {}).get("duration", 0))


def doctor():
    available = {x: shutil.which(x) is not None for x in ["ffmpeg", "ffprobe"]}
    if available["ffmpeg"]:
        available["subtitles_filter"] = " subtitles " in run(["ffmpeg", "-hide_banner", "-filters"]).stdout
    return {"tools": available, "ready": all(available.values()),
            "optional": "faster-whisper and numpy for local transcription"}


def timestamp(seconds, sep=","):
    ms = round(seconds * 1000)
    return f"{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02}{sep}{ms%1000:03}"


def caption_cues(words):
    cues, group = [], []
    last_end = 0.0
    def flush():
        if group:
            text = " ".join(w["word"].strip() for w in group)
            lines = textwrap.wrap(text, width=42, break_long_words=False, break_on_hyphens=False)
            if len(lines) > 2 or any(len(s) > 42 for s in lines):
                raise ValueError("Caption text exceeds two 42-character lines.")
            cues.append({"start": group[0]["start"], "end": group[-1]["end"], "text": "\n".join(lines)})
            group.clear()
    for w in words:
        w = dict(w)
        w["start"], w["end"] = float(w["start"]), float(w["end"])
        if not str(w["word"]).strip():
            continue
        if not math.isfinite(w["start"] + w["end"]) or w["start"] < last_end - 0.001 or w["end"] <= w["start"]:
            raise ValueError("Word timestamps must be finite, positive-duration and non-overlapping.")
        if len(w["word"].strip()) > 42:
            raise ValueError("A caption word exceeds 42 characters; inspect transcription.")
        if group:
            combined = " ".join(x["word"].strip() for x in group + [w])
            lines = textwrap.wrap(combined, 42, break_long_words=False, break_on_hyphens=False)
            if len(lines) > 2 or w["end"] - group[0]["start"] > 6 or w["start"] - group[-1]["end"] > 0.8:
                flush()
        group.append(w)
        last_end = w["end"]
        if re.search(r'[.!?][”"\x27]?$', w["word"].strip()):
            flush()
    flush()
    if not cues:
        raise ValueError("No timed words supplied.")
    return cues


def captions(source, out):
    data = json.loads(Path(source).read_text(encoding="utf-8"))
    cues = caption_cues(data["words"] if isinstance(data, dict) else data)
    out = Path(out)
    targets = [out / name for name in ["captions.srt", "captions.vtt", "caption-cues.json"]]
    if any(p.exists() for p in targets):
        raise ValueError("Caption files already exist; use a new directory.")
    out.mkdir(parents=True, exist_ok=True)
    srt = "\n\n".join(f'{i}\n{timestamp(c["start"])} --> {timestamp(c["end"])}\n{c["text"]}'
                      for i, c in enumerate(cues, 1))
    vtt = "WEBVTT\n\n" + "\n\n".join(f'{timestamp(c["start"], ".")} --> {timestamp(c["end"], ".")}\n{html.escape(c["text"])}'
                                     for c in cues)
    targets[0].write_text(srt + "\n", encoding="utf-8")
    targets[1].write_text(vtt + "\n", encoding="utf-8")
    save(targets[2], cues)
    return {"cues": len(cues), "files": [str(p.resolve()) for p in targets]}


def validate(source, allow_preview=False):
    source = Path(source).resolve()
    spec = json.loads(source.read_text(encoding="utf-8"))
    errors, warnings = [], []
    width, height, fps = spec.get("width", 1920), spec.get("height", 1080), spec.get("fps", 30)
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in [width, height, fps]):
        raise ValueError("width, height and fps must be integers.")
    if width < 2 or height < 2 or width % 2 or height % 2 or not 1 <= fps <= 60:
        raise ValueError("Use positive even dimensions and fps between 1 and 60.")
    spec.update(width=width, height=height, fps=fps)
    shots = spec.get("shots", [])
    if not shots:
        errors.append("No shots.")
    ids, paths, clock = set(), set(), 0.0
    for i, shot in enumerate(shots, 1):
        sid = shot.get("id", "")
        if not sid or sid in ids:
            errors.append(f"Shot {i}: missing/duplicate ID.")
        ids.add(sid)
        dur = float(shot.get("duration", 0))
        offset = float(shot.get("in", 0))
        if not math.isfinite(dur + offset) or dur <= 0 or offset < 0:
            errors.append(f"{sid}: invalid duration/in.")
            continue
        shot["_start_frame"] = round(clock * fps)
        clock += dur
        shot["_frames"] = round(clock * fps) - shot["_start_frame"]
        if shot["_frames"] < 1:
            errors.append(f"{sid}: shorter than one output frame.")
        path = source.parent / shot.get("path", "")
        shot["_path"] = str(path.resolve())
        if not path.is_file():
            errors.append(f"{sid}: missing media.")
            continue
        if shot["_path"] in paths:
            warnings.append(f"{sid}: repeated asset; verify intentional reuse.")
        paths.add(shot["_path"])
        if shot.get("kind") not in ["image", "video"]:
            errors.append(f"{sid}: kind must be image/video.")
        if shot.get("fit", "contain") not in ["contain", "cover"]:
            errors.append(f"{sid}: fit must be contain/cover.")
        if not shot.get("source_url") or not shot.get("license"):
            errors.append(f"{sid}: missing source/license record.")
        if shot.get("kind") == "image" and dur > 12:
            warnings.append(f"{sid}: still held {dur:.1f}s; review pacing.")
        info = probe(path)
        video = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
        if video is None:
            errors.append(f"{sid}: no visual stream.")
            continue
        small = video["width"] < width or video["height"] < height
        if small or shot.get("preview"):
            message = f"{sid}: preview/undersized asset ({video['width']}x{video['height']})."
            (warnings if allow_preview else errors).append(message)
        if shot.get("kind") == "video" and offset + shot["_frames"]/fps > duration(info) + 0.04:
            errors.append(f"{sid}: trim extends past source.")
    spec["_duration"] = round(clock * fps) / fps
    for key in ["narration", "captions"]:
        value = spec.get(key)
        if not value:
            if key == "narration": errors.append("Narration required.")
            else: warnings.append("No captions supplied.")
            continue
        path = source.parent / value
        spec["_" + key] = str(path.resolve())
        if not path.is_file():
            errors.append(f"Missing {key}.")
        elif key == "narration":
            info = probe(path)
            if not any(s["codec_type"] == "audio" for s in info["streams"]):
                errors.append("Narration has no audio stream.")
            if abs(duration(info) - spec["_duration"]) > 0.25:
                errors.append(f"Audio ({duration(info):.3f}s) and shots ({spec['_duration']:.3f}s) differ by >0.25s.")
        elif key == "captions":
            if path.suffix.lower() != ".srt":
                errors.append("Burned caption input must be SRT.")
            timings = re.findall(r"(\d+):(\d+):(\d+),(\d+)\s+-->\s+(\d+):(\d+):(\d+),(\d+)", path.read_text(encoding="utf-8"))
            previous = 0
            if not timings:
                errors.append("No valid SRT cue timings.")
            for t in timings:
                a, b = [int(t[j])*3600+int(t[j+1])*60+int(t[j+2])+int(t[j+3])/1000 for j in [0,4]]
                if a < previous or b <= a or b > spec["_duration"] + 0.05:
                    errors.append("Caption timing overlap/outside timeline.")
                    break
                previous = b
    return {"valid": not errors, "errors": errors, "warnings": warnings,
            "duration": spec["_duration"], "preview": bool(allow_preview), "spec": spec}


def render(source, out, allow_preview=False):
    out = Path(out).resolve()
    if out.exists() or out.with_suffix(".render.json").exists():
        raise ValueError("Output/version already exists; choose a new filename.")
    checked = validate(source, allow_preview)
    if not checked["valid"]:
        raise ValueError("\n".join(checked["errors"]))
    spec = checked["spec"]
    w, h, fps = spec["width"], spec["height"], spec["fps"]
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="video-render-", dir=out.parent) as folder:
        temp = Path(folder)
        for i, shot in enumerate(spec["shots"]):
            vf = (f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"
                  if shot.get("fit", "contain") == "contain" else
                  f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}")
            vf += f",setsar=1,fps={fps},format=yuv420p"
            args = ["ffmpeg", "-v", "error", "-nostdin", "-filter_threads", "1"]
            if shot["kind"] == "image":
                args += ["-loop", "1", "-framerate", str(fps)]
            else:
                args += ["-ss", str(shot.get("in", 0))]
            args += ["-i", shot["_path"], "-vf", vf, "-frames:v", str(shot["_frames"]),
                     "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-threads", "2",
                     str(temp / f"shot-{i:04d}.mp4")]
            run(args)
        (temp / "shots.ffconcat").write_text("ffconcat version 1.0\n" + "".join(
            f"file 'shot-{i:04d}.mp4'\n" for i in range(len(spec["shots"]))), encoding="utf-8")
        filters = []
        if spec.get("_captions"):
            shutil.copyfile(spec["_captions"], temp / "captions.srt")
            # ASS defaults use a 384x288 coordinate grid when no PlayRes is supplied.
            style = "FontName=DejaVu Sans,FontSize=15,Outline=1,Shadow=0,MarginV=12,Alignment=2"
            filters.append("subtitles=filename=captions.srt:force_style='" + style + "'")
        if allow_preview:
            filters.append("drawtext=text='ASSEMBLY PREVIEW':fontsize=h/35:fontcolor=white:box=1:boxcolor=black@0.65:x=20:y=20")
        args = ["ffmpeg", "-v", "error", "-nostdin", "-filter_threads", "1",
                "-f", "concat", "-safe", "1", "-i", "shots.ffconcat", "-i", spec["_narration"],
                "-map", "0:v:0", "-map", "1:a:0"]
        if filters:
            args += ["-vf", ",".join(filters), "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-threads", "2"]
        else:
            args += ["-c:v", "copy"]
        args += ["-c:a", "aac", "-b:a", "192k", "-t", str(spec["_duration"]), "-movflags", "+faststart", str(temp / "output.mp4")]
        run(args, cwd=temp)
        shutil.move(str(temp / "output.mp4"), out)
    report = {k: v for k, v in checked.items() if k != "spec"}
    report.update(output=str(out), editorial_qa="not_performed")
    save(out.with_suffix(".render.json"), report)
    return report


def qa(source, out, expected=None):
    source, out = Path(source).resolve(), Path(out).resolve()
    if out.exists():
        raise ValueError("QA directory exists; use a new version.")
    info = probe(source)
    out.mkdir(parents=True)
    scan = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(source),
                           "-vf", "blackdetect=d=0.15:pix_th=0.10",
                           "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True)
    (out / "scan.log").write_text(scan.stderr, encoding="utf-8")
    decode = subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-nostdin", "-i", str(source),
                             "-f", "null", "-"], capture_output=True, text=True)
    (out / "decode.log").write_text(decode.stderr, encoding="utf-8")
    black = re.findall(r"black_start:([\d.]+) black_end:([\d.]+) black_duration:([\d.]+)", scan.stderr)
    peaks = re.findall(r"max_volume: (-?[\d.]+) dB", scan.stderr)
    peak = float(peaks[-1]) if peaks else None
    length = duration(info)
    samples = [min(length - 0.05, max(0, length * f)) for f in [0, .1, .25, .5, .75, .9, .99]]
    for i, t in enumerate(samples):
        run(["ffmpeg", "-v", "error", "-nostdin", "-ss", str(max(0, t)), "-i", str(source),
             "-frames:v", "1", "-vf", "scale=960:-2", "-threads", "1", str(out / f"frame-{i:02d}.jpg")])
    flags = []
    if scan.returncode: flags.append("Measurement scan failed; inspect scan.log.")
    if decode.returncode or decode.stderr.strip(): flags.append("Decode errors.")
    if black: flags.append("Black intervals detected; inspect whether intentional.")
    if peak is None: flags.append("Audio peak unavailable.")
    elif peak >= 0: flags.append("Audio peak reaches 0 dBFS.")
    if expected is not None and abs(length - expected) > 0.25: flags.append("Duration mismatch.")
    report = {"duration": length, "sample_peak_dbfs": peak, "black_intervals": black,
              "decode_ok": decode.returncode == 0 and not decode.stderr.strip(),
              "scan_ok": scan.returncode == 0, "flags": flags, "probe": info,
              "frame_samples": [{"time": t, "file": f"frame-{i:02d}.jpg"} for i,t in enumerate(samples)],
              "editorial_review": "not_performed", "caption_accuracy": "not_verified",
              "publication_ready": False}
    save(out / "qa.json", report)
    return {k:v for k,v in report.items() if k not in ["probe", "frame_samples"]}


def review(source, out):
    source, out = Path(source).resolve(), Path(out).resolve()
    if out.exists():
        raise ValueError("Review file exists; choose a new version.")
    import os
    relative = quote(os.path.relpath(source, out.parent))
    title = html.escape(source.stem)
    page = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>VIDEO_TITLE — Review</title><style>body{max-width:1000px;margin:30px auto;padding:20px;background:#192c3a;color:#f5f0e8;font:18px system-ui}video{width:100%}textarea{display:block;width:95%;height:70px;margin:16px 0}button{padding:10px;margin:5px;cursor:pointer}li{padding:10px}</style>
<h1>VIDEO_TITLE</h1><p>Assembly review. Notes stay in this browser; export JSON to share feedback.</p>
<video id="v" controls preload="metadata" src="VIDEO_URL"></video>
<label for="note">Note at the current playback position</label><textarea id="note"></textarea>
<button id="add">Add note</button><button id="export">Export notes</button><ol id="notes"></ol>
<script>
const v=document.getElementById('v'),n=document.getElementById('note'),list=document.getElementById('notes');
const key='video-review:'+location.pathname;
let notes=[];try{notes=JSON.parse(localStorage.getItem(key)||'[]')}catch(e){}
function show(){list.replaceChildren();for(const item of notes){const li=document.createElement('li'),b=document.createElement('button');b.textContent=item.time.toFixed(2)+'s';b.onclick=()=>{v.currentTime=item.time};li.append(b,document.createTextNode(item.text));list.append(li)}}
document.getElementById('add').onclick=()=>{if(!n.value.trim())return;notes.push({time:v.currentTime,text:n.value.trim()});try{localStorage.setItem(key,JSON.stringify(notes))}catch(e){}n.value='';show()};
document.getElementById('export').onclick=()=>{const u=URL.createObjectURL(new Blob([JSON.stringify({video:v.getAttribute('src'),notes},null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=u;a.download='review-notes.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)};
show();</script></html>"""
    page = page.replace("VIDEO_TITLE", title).replace("VIDEO_URL", relative)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return {"review": str(out), "video": str(source), "shared_notes": False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    for command in ["captions", "validate", "render", "qa", "review"]:
        q = sub.add_parser(command); q.add_argument("source")
        if command != "validate": q.add_argument("--out", required=True)
        if command in ["validate", "render"]: q.add_argument("--allow-preview", action="store_true")
        if command == "qa": q.add_argument("--expected-duration", type=float)
    a = p.parse_args()
    try:
        if a.command == "doctor": result = doctor()
        elif a.command == "captions": result = captions(a.source, a.out)
        elif a.command == "validate":
            result = validate(a.source, a.allow_preview)
            result.pop("spec")
        elif a.command == "render": result = render(a.source, a.out, a.allow_preview)
        elif a.command == "qa": result = qa(a.source, a.out, a.expected_duration)
        else: result = review(a.source, a.out)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        p.exit(1, f"Error: {exc}\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("valid") is False or result.get("ready") is False:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
