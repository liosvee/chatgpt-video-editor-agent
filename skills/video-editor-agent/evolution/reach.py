#!/usr/bin/env python3
"""Bounded, read-only discovery through the reviewed Agent-Reach v1 JSON envelope."""
import argparse
import json
import shutil
import subprocess

if __package__:
    from .learn import Learning, digest, now, read, require, text, write
else:
    from learn import Learning, digest, now, read, require, text, write

CHANNELS = ("youtube", "web", "reddit", "twitter", "bilibili", "xiaohongshu", "github")
UPSTREAM_COMMIT = "14c213405669414492bda0f8d52cc6531d062c45"


def command(channel, query, limit):
    require(channel in CHANNELS, "Unsupported channel.")
    require(type(limit) is int and 1 <= limit <= 20, "Limit must be 1 to 20.")
    text(query, "query", 500)
    return ["agent-reach", channel, "search", "--limit", str(limit), "--timeout", "30", "--", query]


def collect(project, channel, query, limit=5, engine=None):
    engine = engine or Learning()
    project, folder, run = engine.current(project)
    require(run["phase"] == "research", "Collect before refresh; begin a new run for new research.")
    argv = command(channel, query, limit)
    request = {"channel": channel, "query": query, "limit": limit}
    target = folder / "raw" / ("agent-reach-" + digest(request)[:20] + ".json")
    if target.exists():
        return {"file": str(target.relative_to(project)), "status": read(target)["status"], "cached": True}
    # An interrupted request stays checkpointed; no automatic retry even after a timeout.
    record = {"provider": "agent-reach", "request": request, "collected_at": now(),
              "adapter_reference_commit": UPSTREAM_COMMIT, "status": "interrupted", "response": None}
    write(target, record)
    try:
        exe = shutil.which("agent-reach")
        if not exe:
            record["status"] = "unavailable"
            record["error_code"] = "NEED_SETUP"
        else:
            argv[0] = exe
            result = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45, shell=False)
            require(len(result.stdout.encode()) <= 5_000_000, "Response exceeds limit.")
            response = json.loads(result.stdout)
            require(type(response.get("schema_version")) is int and response["schema_version"] == 1,
                    "Unsupported Agent-Reach schema.")
            require(response.get("channel") == channel and response.get("action") == "search" and type(response.get("ok")) is bool,
                    "Unexpected Agent-Reach envelope.")
            if response["ok"]:
                require(result.returncode == 0 and isinstance(response.get("items"), list), "Invalid successful response.")
                record.update(status="ok" if response["items"] else "empty", response=response)
            else:
                record.update(status="unavailable", error_code="UPSTREAM_UNAVAILABLE")
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
        record.update(status="error", error_code="UNSUPPORTED_RESPONSE_OR_TIMEOUT")
    write(target, record)
    return {"file": str(target.relative_to(project)), "status": record["status"], "cached": False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("project"); p.add_argument("--channel", choices=CHANNELS, default="youtube")
    p.add_argument("--query", required=True); p.add_argument("--limit", type=int, default=5)
    a = p.parse_args()
    try:
        print(json.dumps(collect(a.project, a.channel, a.query, a.limit), indent=2))
    except (ValueError, KeyError, OSError) as exc:
        p.exit(1, "Agent-Reach collection: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
