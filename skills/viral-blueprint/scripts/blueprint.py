#!/usr/bin/env python3
"""Turn the most-viewed videos in a niche into a blueprint for an original, improved video.

    python3 blueprint.py select <vidiq-response.json>... --format long|short -o <project>/viral/selection.json
    python3 blueprint.py dissect <selection.json> --video <id> --transcript <transcript.json|txt> -o <project>/viral/blueprint.json
    python3 blueprint.py check <blueprint.json> --script <script.md> [--title "..."] [--upload <upload.json>]

select   reads SAVED vidIQ responses (vidiq_outliers, vidiq_youtube_search, vidiq_get_videos_by_ids),
         merges them by video ID, filters to the declared format and age window, drops your own
         channel, ranks by views (one video per channel by default) and writes the full candidate
         cohort plus the top-N picks. It never calls vidIQ: the agent does that and saves the JSON.
dissect  breaks one picked video into the parts you reuse as a blueprint — never as text to copy:
           script  : runtime, words/min, hook window, beat map in 10 % slices, devices
                     (questions, open loops, lists, contrast turns, CTAs)
           title   : length, number, question, brackets, caps, "you", curiosity/power words,
                     split (colon/dash) and a slot pattern
           metadata: above-the-fold line, links, timestamps, hashtags, tags + their char budget
         Writes blueprint.json and a readable blueprint.md next to it.
check    proves the new video is an improved original, not a copy:
           script  : ERROR on any run of >= 8 consecutive words shared with the source transcript;
                     WARN/ERROR when 4-gram overlap passes 5 % / 15 %; WARN when the hook runs long
           title   : ERROR when identical or >= 80 % similar to the source title; reports which
                     source patterns were kept; WARN past 70 chars
           upload  : ERROR on a >= 12-word run copied from the source description, tags > 500 chars,
                     > 60 hashtags; WARN when > 80 % of tags are copied unchanged or > 15 hashtags
Exit status 1 on any ERROR. Standard library only.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SHORT_MAX_S = 180
HOOK_WINDOW_S = {"long": 30.0, "short": 3.0}
COPY_RUN_SCRIPT = 8
COPY_RUN_DESCRIPTION = 12
NGRAM_WARN, NGRAM_ERROR = 0.05, 0.15
TITLE_SIMILAR = 0.80

WORD_RE = re.compile(r"[^\W_]+(?:['’][^\W_]+)?", re.UNICODE)
HASHTAG_RE = re.compile(r"(?<![\w#])#([^\W_][\w]*)", re.UNICODE)
URL_RE = re.compile(r"https?://\S+")
TIMESTAMP_RE = re.compile(r"^\s*(?:\d{1,2}:)?\d{1,2}:\d{2}\b", re.M)
ISO_DUR_RE = re.compile(r"^P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?$")

POWER_WORDS = {"secret", "secrets", "truth", "never", "always", "stop", "why", "how", "nobody", "everyone",
               "dark", "hidden", "real", "brutal", "silent", "silence", "powerful", "dangerous", "mistake",
               "mistakes", "rules", "rule", "habits", "signs", "psychology", "weak", "strong", "rich",
               "instantly", "finally", "exactly", "only", "worst", "best", "ultimate", "simple"}
DEVICES = {
    "open_loop": r"\b(by the end|stay (?:with me|until)|later (?:in this|i'?ll)|in a (?:minute|moment)|but first|wait until|here'?s the (?:thing|twist|catch))\b",
    "contrast": r"\b(but|however|instead|the truth is|what (?:they|nobody) (?:don'?t|won'?t) tell)\b",
    "list": r"\b(first|second|third|fourth|fifth|number (?:one|two|three|\d+)|step \d+|rule \d+|sign \d+|#\d+)\b",
    "cta": r"\b(subscribe|like (?:this|the) video|comment|link (?:in|below)|follow for|share this)\b",
    "you_address": r"\b(you|your|you'?re|yourself)\b",
}


def die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(2)


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        die(f"cannot read {path}: {exc}")


CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")


def words(text):
    return [w.lower().replace("’", "'") for w in WORD_RE.findall(text or "")]


def is_cjk(text):
    return len(CJK_RE.findall(text or "")) > len(text or "") * 0.2


def tokens(text, cjk):
    """Comparison units: words for space-separated languages, characters for Japanese/Korean/Chinese."""
    if cjk:
        return [c for c in (text or "") if not c.isspace() and (c.isalnum() or CJK_RE.match(c))]
    return words(text)


# copy-detection thresholds per unit: (shared run that is a copy, n-gram size)
UNITS = {False: {"script_run": COPY_RUN_SCRIPT, "desc_run": COPY_RUN_DESCRIPTION, "n": 4, "unit": "words"},
         True: {"script_run": 15, "desc_run": 25, "n": 8, "unit": "characters"}}


def seconds(value):
    """Duration from seconds, "12:34", "1:02:03" or ISO-8601 "PT12M34S"; None if unknown."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        return float(text)
    if re.fullmatch(r"\d+(?::\d{1,2}){1,2}", text):
        total = 0.0
        for part in text.split(":"):
            total = total * 60 + int(part)
        return total
    m = ISO_DUR_RE.match(text)
    if m and any(m.groups()):
        d, h, mi, s = (float(g) if g else 0.0 for g in m.groups())
        return d * 86400 + h * 3600 + mi * 60 + s
    return None


def parse_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def number(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


# ---------------------------------------------------------------- select

def first(d, *keys):
    for key in keys:
        cur = d
        for part in key.split("."):
            cur = cur.get(part) if isinstance(cur, dict) else None
        if cur not in (None, ""):
            return cur
    return None


def walk_videos(node, source):
    """Yield every dict in a saved response that looks like a video record."""
    if isinstance(node, list):
        for item in node:
            yield from walk_videos(item, source)
    elif isinstance(node, dict):
        vid = first(node, "videoId", "id.videoId", "id")
        if isinstance(vid, str) and re.fullmatch(r"[A-Za-z0-9_-]{11}", vid) and \
                (first(node, "title", "snippet.title") or first(node, "viewCount", "statistics.viewCount", "views")):
            yield vid, node, source
        for value in node.values():
            if isinstance(value, (list, dict)):
                yield from walk_videos(value, source)


def normalize(vid, raw, source):
    tags = first(raw, "tags", "snippet.tags")
    return {
        "id": vid,
        "url": f"https://www.youtube.com/watch?v={vid}",
        "title": first(raw, "title", "snippet.title"),
        "channelId": first(raw, "channelId", "snippet.channelId", "channel.id"),
        "channelTitle": first(raw, "channelTitle", "channelName", "snippet.channelTitle", "channel.title"),
        "publishedAt": first(raw, "publishedAt", "snippet.publishedAt", "published_at"),
        "viewCount": number(first(raw, "viewCount", "statistics.viewCount", "views")),
        "vph": number(first(raw, "vph", "viewsPerHour")),
        "outlierScore": number(first(raw, "outlierScore", "breakoutScore", "score")),
        "durationSeconds": seconds(first(raw, "durationSeconds", "duration", "contentDetails.duration", "lengthSeconds")),
        "description": first(raw, "description", "snippet.description"),
        "tags": tags if isinstance(tags, list) else None,
        "thumbnail": first(raw, "thumbnail", "thumbnailUrl", "thumbnails.high.url", "snippet.thumbnails.high.url"),
        "sources": [source],
    }


def merge(old, new):
    for key, value in new.items():
        if key == "sources":
            old["sources"] = sorted(set(old["sources"]) | set(value))
        elif value not in (None, "", []) and (old.get(key) in (None, "", []) or key in ("viewCount", "vph")):
            old[key] = value  # later responses (get_videos_by_ids refresh) carry fresher stats
    return old


def cmd_select(args):
    now = parse_time(args.now) if args.now else datetime.now(timezone.utc)
    pool = {}
    for path in args.responses:
        for vid, raw, source in walk_videos(load_json(path), Path(path).name):
            rec = normalize(vid, raw, source)
            pool[vid] = merge(pool[vid], rec) if vid in pool else rec
    if not pool:
        die("no video records found in the saved responses")
    exclude = {c.lower().lstrip("@") for c in args.exclude_channel}
    candidates = []
    for rec in pool.values():
        reasons = []
        dur = rec["durationSeconds"]
        if dur is None:
            rec["formatVerified"] = False
        else:
            rec["formatVerified"] = True
            is_short = dur <= SHORT_MAX_S
            if (args.format == "short") != is_short:
                reasons.append(f"format: {dur:.0f}s is not {args.format}")
        published = parse_time(rec["publishedAt"])
        rec["ageDays"] = round((now - published).total_seconds() / 86400, 1) if published else None
        if args.max_age_days and rec["ageDays"] is not None and rec["ageDays"] > args.max_age_days:
            reasons.append(f"age {rec['ageDays']}d > {args.max_age_days}d")
        if args.min_age_days and rec["ageDays"] is not None and rec["ageDays"] < args.min_age_days:
            reasons.append(f"age {rec['ageDays']}d < {args.min_age_days}d (views not settled)")
        if {str(rec["channelId"] or "").lower(), str(rec["channelTitle"] or "").lower().lstrip("@")} & exclude:
            reasons.append("own channel")
        if rec["viewCount"] is None:
            reasons.append("no view count (refresh with vidiq_get_videos_by_ids)")
        rec["excluded"] = reasons
        candidates.append(rec)
    eligible = sorted((c for c in candidates if not c["excluded"]), key=lambda c: -c["viewCount"])
    picks, per_channel = [], {}
    for rec in eligible:
        key = rec["channelId"] or rec["channelTitle"] or rec["id"]
        if per_channel.get(key, 0) >= args.per_channel:
            continue
        per_channel[key] = per_channel.get(key, 0) + 1
        picks.append(rec)
        if len(picks) >= args.top:
            break
    unverified = [p["id"] for p in picks if not p["formatVerified"]]
    out = {
        "schema": "viral-blueprint/selection@1",
        "collectedAt": now.isoformat(timespec="seconds"),
        "cohort": {"niche": args.niche, "format": args.format, "language": args.language,
                   "minAgeDays": args.min_age_days, "maxAgeDays": args.max_age_days,
                   "rankingMetric": "viewCount", "perChannel": args.per_channel, "top": args.top,
                   "responses": [Path(p).name for p in args.responses]},
        "caveat": "Most-viewed within this sampled cohort only; views are not CTR, retention or proof of why it worked.",
        "picks": [p["id"] for p in picks],
        "formatUnverified": unverified,
        "candidates": sorted(candidates, key=lambda c: -(c["viewCount"] or -1)),
    }
    write_json(args.output, out)
    print(f"{len(candidates)} candidates, {len(eligible)} eligible, picked {len(picks)} by views:")
    for p in picks:
        flag = "" if p["formatVerified"] else "  [duration unknown: verify format]"
        print(f"  {int(p['viewCount']):>12,}  {p['id']}  {p['title']!s:.70}  ({p['channelTitle']}){flag}")
    return 0 if picks else 1


# ---------------------------------------------------------------- dissect

def load_transcript(path):
    """Return [(start_seconds, text)] from a vidIQ transcript JSON, a list of segments, SRT/VTT or plain text."""
    text = Path(path).read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None
    if data is not None:
        segs = []

        def visit(node):
            if isinstance(node, list):
                for item in node:
                    visit(item)
            elif isinstance(node, dict):
                body = node.get("text") or node.get("snippet") or node.get("content")
                start = next((node[k] for k in ("start", "offset", "startTime", "start_seconds", "startMs") if k in node), None)
                if isinstance(body, str) and start is not None:
                    s = seconds(start) if not isinstance(start, (int, float)) else float(start)
                    if "startMs" in node and s is not None:
                        s /= 1000
                    segs.append((s or 0.0, body))
                    return
                for value in node.values():
                    if isinstance(value, (list, dict)):
                        visit(value)
                    elif isinstance(value, str) and len(value) > 200 and not segs:
                        segs.append((0.0, value))

        visit(data)
        if segs:
            return sorted(segs, key=lambda s: s[0])
        if isinstance(data, dict) and isinstance(data.get("transcript"), str):
            return [(0.0, data["transcript"])]
    segs, cur = [], None
    for line in text.splitlines():
        m = re.match(r"^\s*(\d{1,2}:)?(\d{1,2}):(\d{2})[.,]?\d*\s*(?:-->.*)?$", line)
        m2 = re.match(r"^\s*\[?((?:\d{1,2}:)?\d{1,2}:\d{2})\]?\s+(.+)$", line)
        if m:
            cur = seconds(line.split("-->")[0].strip().split(".")[0].split(",")[0])
        elif m2:
            segs.append((seconds(m2.group(1)), m2.group(2)))
        elif line.strip() and not line.strip().isdigit() and line.strip() != "WEBVTT":
            segs.append((cur if cur is not None else 0.0, line.strip()))
            cur = None
    return segs or [(0.0, text)]


def device_counts(text):
    low = text.lower()
    out = {name: len(re.findall(rx, low)) for name, rx in DEVICES.items()}
    out["questions"] = text.count("?")
    return out


def dissect_script(segs, duration, fmt):
    timed = any(s for s, _ in segs[1:]) and duration
    full = " ".join(t for _, t in segs)
    total_words = len(words(full))
    end = duration or (segs[-1][0] if timed else None)
    wpm = round(total_words / (end / 60), 1) if end else None
    hook_s = HOOK_WINDOW_S[fmt]
    if timed:
        hook_text = " ".join(t for s, t in segs if s < hook_s)
    else:
        rate = (wpm or 150) / 60
        hook_text = " ".join(words(full)[: max(1, int(hook_s * rate))])
    beats = []
    if timed:
        for i in range(10):
            lo, hi = end * i / 10, end * (i + 1) / 10
            part = " ".join(t for s, t in segs if lo <= s < hi)
            beats.append(beat(i, lo, part))
    else:
        toks = full.split()
        for i in range(10):
            part = " ".join(toks[len(toks) * i // 10: len(toks) * (i + 1) // 10])
            beats.append(beat(i, None, part))
    cjk = is_cjk(full)
    chars = len(tokens(full, True))
    return {
        "words": total_words,
        "language_units": "characters" if cjk else "words",
        "characters": chars,
        "charactersPerSecond": round(chars / end, 2) if (cjk and end) else None,
        "durationSeconds": end,
        "wordsPerMinute": wpm,
        "timed": bool(timed),
        "hook": {"windowSeconds": hook_s, "words": len(words(hook_text)), "devices": device_counts(hook_text),
                 "opensWithQuestion": "?" in hook_text[:200], "addressesYou": bool(re.search(DEVICES["you_address"], hook_text.lower()))},
        "devices": device_counts(full),
        "beats": beats,
    }


def beat(i, start, text):
    ws = text.split()
    return {"slice": f"{i * 10}-{(i + 1) * 10}%", "start": round(start, 1) if start is not None else None,
            "words": len(ws), "devices": {k: v for k, v in device_counts(text).items() if v},
            "gist": " ".join(ws[:12]) + (" …" if len(ws) > 12 else "")}


def dissect_title(title):
    t = title or ""
    ws = words(t)
    patterns = []
    if re.search(r"\d", t):
        patterns.append("number")
    if "?" in t:
        patterns.append("question")
    if re.search(r"[\(\[]", t):
        patterns.append("brackets")
    if re.search(r"\s[:|—–-]\s|:\s", t):
        patterns.append("split")
    caps = [w for w in re.findall(r"\b[A-Z]{3,}\b", t)]
    if caps:
        patterns.append("caps_emphasis")
    if {"you", "your", "you're"} & set(ws):
        patterns.append("you")
    if ws and ws[0] in {"how", "why", "what", "when", "this", "these", "stop", "never", "the"}:
        patterns.append(f"opens_{ws[0]}")
    power = sorted(set(ws) & POWER_WORDS)
    if re.search(r"\b(nobody|no one|they don'?t|won'?t tell|secret|hidden|truth)\b", t.lower()):
        patterns.append("curiosity_gap")
    slots = re.sub(r"\d+", "{N}", t)
    return {"title": t, "chars": len(t), "words": len(ws), "patterns": patterns, "powerWords": power,
            "capsWords": caps, "slotPattern": slots}


def dissect_metadata(rec):
    desc = rec.get("description") or ""
    tags = rec.get("tags") or []
    lines = [ln for ln in desc.splitlines() if ln.strip()]
    title_words = set(words(rec.get("title"))) - {"the", "a", "an", "of", "to", "and", "in", "is", "you", "your"}
    return {
        "descriptionChars": len(desc),
        "aboveTheFold": desc[:150],
        "aboveFoldHasTitleKeyword": bool(title_words & set(words(desc[:150]))),
        "lines": len(lines),
        "links": len(URL_RE.findall(desc)),
        "timestamps": len(TIMESTAMP_RE.findall(desc)),
        "hashtags": ["#" + h for h in HASHTAG_RE.findall(desc)],
        "tags": tags,
        "tagCount": len(tags),
        "tagChars": sum(len(t) for t in tags) + max(0, len(tags) - 1),
        "tagsAvailable": rec.get("tags") is not None,
    }


def cmd_dissect(args):
    sel = load_json(args.selection)
    fmt = sel.get("cohort", {}).get("format", "long")
    rec = next((c for c in sel.get("candidates", []) if c["id"] == args.video), None)
    if rec is None:
        die(f"{args.video} is not in {args.selection}")
    segs = load_transcript(args.transcript)
    out = {
        "schema": "viral-blueprint/blueprint@1",
        "source": {k: rec.get(k) for k in ("id", "url", "title", "channelTitle", "publishedAt", "viewCount", "vph", "outlierScore", "durationSeconds")},
        "format": fmt,
        "script": dissect_script(segs, rec.get("durationSeconds"), fmt),
        "title": dissect_title(rec.get("title")),
        "metadata": dissect_metadata(rec),
        "sourceTranscript": " ".join(t for _, t in segs),
        "sourceDescription": rec.get("description") or "",
        "note": "Evidence for structure only. Never reuse the transcript, title wording, description or thumbnail art.",
    }
    write_json(args.output, out)
    md = Path(args.output).with_suffix(".md")
    md.write_text(render_md(out), encoding="utf-8")
    print(f"wrote {args.output} and {md}")
    return 0


def render_md(b):
    s, t, m, src = b["script"], b["title"], b["metadata"], b["source"]
    views = f"{int(src['viewCount']):,}" if src.get("viewCount") else "?"
    out = [f"# Blueprint — {src['title']}", "",
           f"Source: {src['url']} · {src.get('channelTitle')} · {views} views · {b['format']}", "",
           "## Script structure",
           f"- {s['words']} words, {s['durationSeconds'] or '?'} s, {s['wordsPerMinute'] or '?'} wpm",
           f"- Hook (first {s['hook']['windowSeconds']:.0f} s): {s['hook']['words']} words; "
           f"question={s['hook']['opensWithQuestion']}, addresses you={s['hook']['addressesYou']}",
           f"- Devices across the script: {json.dumps(s['devices'])}", "",
           "| slice | start | words | devices | gist (do not reuse) |", "|---|---|---|---|---|"]
    for bt in s["beats"]:
        out.append(f"| {bt['slice']} | {bt['start'] if bt['start'] is not None else '–'} | {bt['words']} | "
                   f"{', '.join(f'{k}:{v}' for k, v in bt['devices'].items()) or '–'} | {bt['gist']} |")
    out += ["", "## Title anatomy",
            f"- {t['chars']} chars, {t['words']} words; patterns: {', '.join(t['patterns']) or 'none'}",
            f"- power words: {', '.join(t['powerWords']) or 'none'}; slot pattern: `{t['slotPattern']}`", "",
            "## Description, hashtags, tags",
            f"- {m['descriptionChars']} chars, {m['lines']} lines, {m['links']} links, {m['timestamps']} timestamps",
            f"- above the fold has a title keyword: {m['aboveFoldHasTitleKeyword']}",
            f"- hashtags ({len(m['hashtags'])}): {' '.join(m['hashtags']) or 'none'}",
            f"- tags ({m['tagCount']}, {m['tagChars']} chars): {', '.join(m['tags']) if m['tagsAvailable'] else 'unavailable'}",
            ""]
    return "\n".join(out)


# ---------------------------------------------------------------- check

def spoken_text(path):
    lines = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("<!--") or re.fullmatch(r"\[[^\]]*\]", s):
            continue
        lines.append(re.sub(r"\[[^\]]*\]", " ", s))
    return " ".join(lines)


def shared_text(a, b, run, cjk):
    _, text = longest_shared_run(a, b)
    return text.replace(" ", "") if cjk else text


def longest_shared_run(a, b):
    """Length and text of the longest run of consecutive tokens common to token lists a and b."""
    best, end_a = 0, 0
    prev = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        ai = a[i - 1]
        for j in range(1, len(b) + 1):
            if ai == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best:
                    best, end_a = cur[j], i
        prev = cur
    return best, " ".join(a[end_a - best:end_a])


def ngram_overlap(a, b, n=4):
    grams = lambda ws: {tuple(ws[i:i + n]) for i in range(len(ws) - n + 1)}  # noqa: E731
    ga, gb = grams(a), grams(b)
    return len(ga & gb) / len(ga) if ga else 0.0


def cmd_check(args):
    b = load_json(args.blueprint)
    findings = []
    add = lambda level, area, msg: findings.append({"level": level, "area": area, "message": msg})  # noqa: E731

    if args.script:
        spoken = spoken_text(args.script)
        cjk = is_cjk(spoken) or is_cjk(b.get("sourceTranscript"))
        u = UNITS[cjk]
        new, src = tokens(spoken, cjk), tokens(b.get("sourceTranscript"), cjk)
        if not new:
            add("ERROR", "script", "script has no spoken text")
        else:
            run, _ = longest_shared_run(new, src)
            if run >= u["script_run"]:
                text = shared_text(new, src, run, cjk)
                add("ERROR", "script", f"{run} consecutive {u['unit']} copied from the source: “{text}” — rewrite in the channel voice")
            ov = ngram_overlap(new, src, u["n"])
            if ov > NGRAM_ERROR:
                add("ERROR", "script", f"{ov:.0%} of {u['n']}-{u['unit'][:-1]} phrases also appear in the source (max {NGRAM_ERROR:.0%})")
            elif ov > NGRAM_WARN:
                add("WARN", "script", f"{ov:.0%} of {u['n']}-{u['unit'][:-1]} phrases also appear in the source; aim under {NGRAM_WARN:.0%}")
            bp = b["script"]
            budget = bp["hook"]["words"]
            opening = re.split(r"(?<=[.!?。！？])\s*", spoken.strip(), maxsplit=1)[0]
            hook_len = len(tokens(opening, cjk)) if cjk else len(words(opening))
            if budget and not cjk and hook_len > budget * 1.5 + 5:
                add("WARN", "script", f"opening sentence is {hook_len} words; the source hook landed in ~{budget} — tighten it")
            if bp.get("wordsPerMinute") and not cjk:
                est = len(new) / bp["wordsPerMinute"] * 60
                if b["format"] == "short" and est > SHORT_MAX_S:
                    add("ERROR", "script", f"~{est:.0f} s at the source pace: too long for a Short (max {SHORT_MAX_S} s)")

    src_title = b["title"]["title"]
    title = args.title
    upload = load_json(args.upload) if args.upload else {}
    title = title or upload.get("title")
    if title:
        ratio = difflib.SequenceMatcher(None, title.lower().strip(), src_title.lower().strip()).ratio()
        if ratio >= 0.999:
            add("ERROR", "title", "title is identical to the source video's title")
        elif ratio >= TITLE_SIMILAR:
            add("ERROR", "title", f"title is {ratio:.0%} similar to the source title; keep the pattern, change the words")
        kept = set(dissect_title(title)["patterns"]) & set(b["title"]["patterns"])
        dropped = set(b["title"]["patterns"]) - kept
        add("INFO", "title", f"kept source patterns: {', '.join(sorted(kept)) or 'none'}; dropped: {', '.join(sorted(dropped)) or 'none'}")
        if len(title) > 70:
            add("WARN", "title", f"title is {len(title)} chars; past ~70 it is cut off in search and suggested")

    if upload:
        desc = upload.get("description", "")
        cjk = is_cjk(desc) or is_cjk(b.get("sourceDescription"))
        u = UNITS[cjk]
        mine, theirs = tokens(desc, cjk), tokens(b.get("sourceDescription"), cjk)
        run, _ = longest_shared_run(mine, theirs)
        if run >= u["desc_run"]:
            add("ERROR", "description", f"{run} consecutive {u['unit']} copied from the source description: “{shared_text(mine, theirs, run, cjk)}”")
        tags = [t.strip().lower() for t in upload.get("tags") or []]
        chars = sum(len(t) for t in tags) + max(0, len(tags) - 1)
        if chars > 500:
            add("ERROR", "tags", f"tags total {chars} chars (max 500)")
        src_tags = {t.strip().lower() for t in b["metadata"].get("tags") or []}
        if tags and src_tags:
            copied = sum(t in src_tags for t in tags) / len(tags)
            if copied > 0.8:
                add("WARN", "tags", f"{copied:.0%} of tags copied unchanged; add your own keyword research and channel terms")
        hashtags = HASHTAG_RE.findall(desc)
        if len(hashtags) > 60:
            add("ERROR", "hashtags", f"{len(hashtags)} hashtags: over 60 and YouTube ignores all of them")
        elif len(hashtags) > 15:
            add("WARN", "hashtags", f"{len(hashtags)} hashtags; 3-5 relevant ones work better")

    errors = sum(f["level"] == "ERROR" for f in findings)
    for f in findings:
        print(f"{f['level']:5}  {f['area']:<11} {f['message']}")
    print(f"\n{errors} error(s), {sum(f['level'] == 'WARN' for f in findings)} warning(s)")
    if args.output:
        write_json(args.output, {"schema": "viral-blueprint/check@1", "source": b["source"]["id"], "findings": findings})
    return 1 if errors else 0


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("select", help="rank saved vidIQ results by views")
    s.add_argument("responses", nargs="+")
    s.add_argument("--format", choices=["long", "short"], required=True)
    s.add_argument("--niche", default=None)
    s.add_argument("--language", default=None)
    s.add_argument("--top", type=int, default=3)
    s.add_argument("--per-channel", type=int, default=1)
    s.add_argument("--min-age-days", type=float, default=3)
    s.add_argument("--max-age-days", type=float, default=None)
    s.add_argument("--exclude-channel", action="append", default=[], help="your own channel ID or handle (repeatable)")
    s.add_argument("--now", help=argparse.SUPPRESS)
    s.add_argument("-o", "--output", required=True)
    d = sub.add_parser("dissect", help="break one picked video into a blueprint")
    d.add_argument("selection")
    d.add_argument("--video", required=True)
    d.add_argument("--transcript", required=True)
    d.add_argument("-o", "--output", required=True)
    c = sub.add_parser("check", help="prove the new video is an improved original")
    c.add_argument("blueprint")
    c.add_argument("--script")
    c.add_argument("--title")
    c.add_argument("--upload")
    c.add_argument("-o", "--output")
    args = p.parse_args(argv)
    return {"select": cmd_select, "dissect": cmd_dissect, "check": cmd_check}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
