#!/usr/bin/env python3
"""Offline checkpoints, narration splitting and provider-unit cost records."""
import argparse
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

STAGES = ["research", "script", "storyboard", "narration", "visuals", "captions", "timeline", "render", "qa"]


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def init(root, title):
    root = Path(root).resolve()
    if (root / "project.json").exists():
        raise ValueError("Project already exists; use status to resume.")
    write(root / "project.json", {"schema_version": 1, "title": title, "created": now(),
          "stages": {}, "history": []})
    write(root / "costs.json", {"operations": []})
    return {"project": str(root), "title": title}


def record(root, stage, artifact, approved=False, evidence=None):
    root, artifact = Path(root).resolve(), Path(artifact).resolve()
    if not artifact.is_file():
        raise ValueError("Artifact must be an existing file.")
    if approved and not evidence:
        raise ValueError("Approved status requires actual user approval evidence.")
    state = read(root / "project.json")
    old = state["stages"].get(stage)
    sha = digest(artifact)
    # Preserve authorization only for exactly unchanged content.
    changed = old is None or old["sha256"] != sha
    if changed:
        for downstream in STAGES[STAGES.index(stage) + 1:]:
            if downstream in state["stages"]:
                state["stages"][downstream]["stale"] = True
                state["stages"][downstream]["approved"] = False
    try:
        saved_path = str(artifact.relative_to(root))
    except ValueError:
        saved_path = str(artifact)
    state["stages"][stage] = {
        "path": saved_path, "sha256": sha, "stale": False, "updated": now(),
        "approved": approved or (not changed and bool(old.get("approved"))),
        "approval_evidence": evidence if approved else (old.get("approval_evidence") if not changed else None)}
    state["history"].append({"at": now(), "stage": stage, "sha256": sha, "changed": changed})
    write(root / "project.json", state)
    return state["stages"][stage]


def status(root):
    root = Path(root).resolve()
    state = read(root / "project.json")
    affected = False
    results = {}
    for name in STAGES:
        item = state["stages"].get(name)
        if not item:
            results[name] = {"status": "not_recorded"}
            continue
        path = root / item["path"]
        valid = path.is_file() and digest(path) == item["sha256"]
        if not valid or item.get("stale"):
            affected = True
        results[name] = {"status": "stale" if affected else "ready",
                         "approved": item.get("approved", False) and not affected,
                         "path": str(path)}
    return {"title": state["title"], "stages": results,
            "costs": read(root / "costs.json")}


def split_text(text, limit):
    """Preserve every character; split only at whitespace and avoid breaking words."""
    if limit < 1:
        raise ValueError("max-chars must be positive.")
    parts = []
    while len(text) > limit:
        window = text[:limit + 1]
        positions = [m.end() for m in re.finditer(r"\n\s*\n", window) if m.end() <= limit]
        if not positions:
            positions = [m.end() for m in re.finditer(r'[.!?][”"\x27]?\s+', window)
                         if m.end() <= limit]
        if not positions:
            positions = [m.end() for m in re.finditer(r"\s+", window) if m.end() <= limit]
        if not positions:
            raise ValueError("A word exceeds the request limit; edit the source manually.")
        cut = positions[-1]
        parts.append(text[:cut])
        text = text[cut:]
    if text:
        parts.append(text)
    return parts


def split(source, out, limit, rate):
    source, out = Path(source), Path(out)
    text = source.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("Narration is empty.")
    if rate is not None and (not math.isfinite(rate) or rate < 0):
        raise ValueError("Rate must be finite and nonnegative.")
    parts = split_text(text, limit)
    targets = [out / f"part-{i:02d}.txt" for i in range(1, len(parts) + 1)]
    if any(p.exists() for p in targets) or (out / "split.json").exists():
        raise ValueError("Split output already exists; use a new directory.")
    out.mkdir(parents=True, exist_ok=True)
    for path, part in zip(targets, parts):
        path.write_text(part, encoding="utf-8")
    result = {"source_sha256": digest(source), "words": len(text.split()),
              "characters": len(text), "max_chars": limit, "rate_per_character": rate,
              "estimated_credits": len(text) * rate if rate is not None else None,
              "estimate_only": True, "parts": [
                  {"file": p.name, "characters": len(s),
                   "estimated_credits": len(s) * rate if rate is not None else None}
                  for p, s in zip(targets, parts)]}
    write(out / "split.json", result)
    return result


def cost(root, args):
    path = Path(root) / "costs.json"
    ledger = read(path)
    row = next((r for r in ledger["operations"] if r["id"] == args.id), None)
    amounts = [args.estimated, args.actual, args.refunded]
    if any(v is not None and (not math.isfinite(v) or v < 0) for v in amounts):
        raise ValueError("Amounts must be finite and nonnegative.")
    if (args.actual is not None or args.refunded is not None) and not args.evidence:
        raise ValueError("Actual/refunded amounts require receipt evidence.")
    if row is None:
        row = {"id": args.id, "provider": args.provider, "unit": args.unit,
               "estimated": None, "actual": None, "refunded": None, "history": []}
        ledger["operations"].append(row)
    if row["provider"] != args.provider or row["unit"] != args.unit:
        raise ValueError("Do not change an operation's provider or unit; use a separate ID.")
    for key in ["estimated", "actual", "refunded", "status", "job_id", "evidence"]:
        value = getattr(args, key)
        if value is not None:
            row[key] = value
    row["updated"] = now()
    row["history"].append({k: v for k, v in row.items() if k != "history"})
    write(path, ledger)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init"); p.add_argument("project"); p.add_argument("--title", required=True)
    p = sub.add_parser("status"); p.add_argument("project")
    p = sub.add_parser("record")
    p.add_argument("project"); p.add_argument("stage", choices=STAGES); p.add_argument("artifact")
    p.add_argument("--approved", action="store_true"); p.add_argument("--evidence")
    p = sub.add_parser("split")
    p.add_argument("source"); p.add_argument("--out", required=True)
    p.add_argument("--max-chars", type=int, required=True); p.add_argument("--rate", type=float)
    p = sub.add_parser("cost")
    p.add_argument("project"); p.add_argument("--id", required=True)
    p.add_argument("--provider", required=True); p.add_argument("--unit", required=True)
    p.add_argument("--status", required=True, choices=["estimated", "submitted", "succeeded", "failed", "refunded"])
    for key in ["estimated", "actual", "refunded"]:
        p.add_argument("--" + key, type=float)
    p.add_argument("--job-id"); p.add_argument("--evidence")
    a = parser.parse_args()
    try:
        if a.command == "init": result = init(a.project, a.title)
        elif a.command == "status": result = status(a.project)
        elif a.command == "record": result = record(a.project, a.stage, a.artifact, a.approved, a.evidence)
        elif a.command == "split": result = split(a.source, a.out, a.max_chars, a.rate)
        else: result = cost(a.project, a)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
