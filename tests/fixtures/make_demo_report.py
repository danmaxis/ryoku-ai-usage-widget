#!/usr/bin/env python3
"""Print a SYNTHETIC `ai-usagebar usage --json` report (schema 1) on stdout.

Every number, plan and message here is invented. It exists so the public
preview image can be a real capture of the popout without showing anyone's real
usage: feed it to `ai-usage/bin/ai-usage-collect --from-file`. Timestamps are
relative to "now" so nothing in the capture reads as stale by accident.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

NOW = datetime.now(timezone.utc).replace(microsecond=0)


def iso(delta: timedelta) -> str:
    return (NOW + delta).isoformat().replace("+00:00", "Z")


def metric(label, percent, severity, detail, reset_in=None, window=None):
    m = {
        "label": label,
        "percent": percent,
        "value": f"{percent}%",
        "headline": "percent",
        "severity": severity,
        "detail": detail,
        "reset_at": iso(reset_in) if reset_in else None,
    }
    if window:
        m["window_secs"] = window
    return m


def entry(pid, display, short, plan, metrics, status="ready", error=None, stale=False):
    return {
        "id": pid,
        "name": pid,
        "display_name": display,
        "short_name": short,
        "icon": pid,
        "brand": pid,
        "plan": plan,
        "status": status,
        "error": error,
        "stale": stale,
        "fetched_at": None if status == "error" else iso(timedelta(seconds=-40)),
        "reset_credits": None,
        "metrics": metrics,
        "sections": [],
    }


H, D = 3600, 86400
REPORT = {
    "schema_version": 1,
    "primary": "anthropic",
    "entries": [
        entry("anthropic", "Claude", "cld", "Demo plan", [
            metric("Session (5h)", 42, "low", "Resets in 2h 10m · 57% elapsed · 15pts behind",
                   timedelta(hours=2, minutes=10), 5 * H),
            metric("Weekly (7d)", 63, "high", "Resets in 3d 4h · 55% elapsed · 8pts ahead",
                   timedelta(days=3, hours=4), 7 * D),
            metric("Weekly · large model", 78, "high", "Resets in 3d 4h · 55% elapsed · 23pts ahead",
                   timedelta(days=3, hours=4), 7 * D),
            metric("Extra credits", 12, "low", "6 of 50 used", timedelta(days=11)),
        ]),
        entry("openai", "Codex", "cdx", "Demo plan", [
            metric("Session (5h)", 18, "low", "Resets in 4h 2m · 19% elapsed · 1pts behind",
                   timedelta(hours=4, minutes=2), 5 * H),
            metric("Weekly (7d)", 35, "low", "Resets in 5d 1h · 28% elapsed · 7pts ahead",
                   timedelta(days=5, hours=1), 7 * D),
        ]),
        entry("copilot", "GitHub Copilot", "ghc", "Demo plan", [
            metric("Premium requests", 91, "critical", "273 of 300 used", timedelta(days=11)),
            metric("Chat", 4, "low", "8 of 200 used", timedelta(days=11)),
        ]),
        entry("openrouter", "OpenRouter", "or", None, [
            metric("Credits", 56, "low", "5.60 of 10.00 used"),
        ]),
        entry("zai", "Z.AI", "zai", None, [], status="error",
              error="credentials error: no API key set for [zai] (demo)."),
        entry("deepinfra", "DeepInfra", "di", None, [
            metric("Credits", 0, "low", "0.00 of 5.00 used"),
        ]),
        entry("synthetic", "Synthetic", "syn", "Demo plan", [
            metric("Requests (5h)", 27, "low", "Resets in 1h 30m · 70% elapsed · 43pts behind",
                   timedelta(hours=1, minutes=30), 5 * H),
        ], stale=True),
    ],
}

if __name__ == "__main__":
    json.dump(REPORT, __import__("sys").stdout, indent=1, ensure_ascii=False)
    print()
