"""T61 — Codex cache shapes the independent contract tests left uncovered.

Author tests (not D5): the schemaVersion 2 shape and the non-general buckets of
schemaVersion 3, both read the way the Ryoku shell reads them
(`shell/services/AiUsage.qml`, `codexBuckets`).
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

COLLECT = Path(__file__).resolve().parents[1] / "bin" / "ai-usage-collect"
RESET = 1900000000


def _codex(tmp_path, data):
    (tmp_path / "codex-usage.json").write_text(json.dumps(data), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(COLLECT), "--source", "ryoku",
         "--ryoku-cache-dir", str(tmp_path)],
        capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    (provider,) = json.loads(r.stdout)["all"]
    return provider


def _window(minutes, utilization, label=""):
    return {"kind": "x", "label": label, "minutes": minutes, "reset": RESET,
            "utilization": utilization}


def test_schema_2_reads_top_level_windows(tmp_path):
    p = _codex(tmp_path, {
        "schemaVersion": 2, "_plan": "Demo", "_source": "app-server",
        "windows": [_window(300, 0.2), _window(10080, 0.7)],
        "5h-utilization": "", "7d-utilization": ""})
    assert [(m["label"], m["percent"]) for m in p["metrics"]] == [
        ("Session (5h)", 20), ("Weekly (7d)", 70)]
    assert p["plan"] == "Demo"


def test_schema_3_extra_buckets_are_labelled_after_the_general_one(tmp_path):
    p = _codex(tmp_path, {
        "schemaVersion": 3, "_source": "app-server",
        "buckets": [
            {"id": "spark", "label": "Spark", "isGeneral": False,
             "windows": [_window(10080, 0.9)]},
            {"id": "codex", "label": "Codex", "isGeneral": True,
             "windows": [_window(300, 0.1), _window(10080, 0.4)]},
        ],
        "windows": [_window(300, 0.1), _window(10080, 0.4)]})
    assert [(m["label"], m["percent"]) for m in p["metrics"]] == [
        ("Session (5h)", 10), ("Weekly (7d)", 40), ("Spark · Weekly (7d)", 90)]


def test_odd_window_gets_its_own_label(tmp_path):
    p = _codex(tmp_path, {
        "schemaVersion": 3, "_source": "app-server",
        "buckets": [{"id": "codex", "isGeneral": True,
                     "windows": [_window(180, 0.5), _window(2880, 0.25)]}]})
    assert [(m["label"], m["window_secs"]) for m in p["metrics"]] == [
        ("3h", 10800), ("2d", 172800)]


def test_bucket_window_without_utilization_is_not_zero(tmp_path):
    p = _codex(tmp_path, {
        "schemaVersion": 3, "_source": "app-server",
        "buckets": [{"id": "codex", "isGeneral": True,
                     "windows": [_window(300, ""), _window(10080, 0.3)]}]})
    assert [(m["label"], m["percent"]) for m in p["metrics"]] == [("Weekly (7d)", 30)]


def test_only_opencode_is_flagged_as_an_estimate(tmp_path):
    legacy = {"5h-utilization": "1.0000", "5h-reset": "0",
              "7d-utilization": "0.5000", "7d-reset": "0", "_source": "storage"}
    for stem in ("claude", "codex", "opencode"):
        (tmp_path / f"{stem}-usage.json").write_text(json.dumps(legacy), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(COLLECT), "--source", "ryoku",
         "--ryoku-cache-dir", str(tmp_path)],
        capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    providers = json.loads(r.stdout)["all"]
    flags = {p["id"]: p["estimate"] for p in providers}
    assert flags == {"anthropic": False, "openai": False, "opencode": True}
    # The mark is on every metric too, so the primary card and the drawer can
    # draw it; the value itself stays a plain percentage.
    for p in providers:
        assert p["metrics"], p["id"]
        assert all(m["estimate"] is p["estimate"] for m in p["metrics"]), p["id"]
        assert all(not m["value"].startswith("~") for m in p["metrics"]), p["id"]


def _all(tmp_path, files, *extra):
    for stem, data in files.items():
        raw = data if isinstance(data, str) else json.dumps(data)
        (tmp_path / f"{stem}-usage.json").write_text(raw, encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(COLLECT), "--source", "ryoku",
         "--ryoku-cache-dir", str(tmp_path), *extra],
        capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


GOOD = {"5h-utilization": "0.4000", "5h-reset": str(RESET),
        "7d-utilization": "0.2000", "7d-reset": str(RESET), "_source": "oauth"}


@pytest.mark.parametrize("bad", [
    '{"5h-utilization": 1e307, "7d-utilization": "1e308", "_source": "x"}',
    '{"5h-utilization": "0.5", "5h-reset": 1e999, "_source": "x"}',
    '{"5h-utilization": "0.5", "5h-reset": "inf", "_source": "x"}',
    '{"schemaVersion": 1e999, "windows": [], "_source": "x"}',
    '{"schemaVersion": 3, "buckets": [{"isGeneral": true, "windows": '
    '[{"minutes": 1e999, "utilization": 0.5, "reset": 1}]}], "_source": "x"}',
    "[" * 100000,
], ids=["huge-utilization", "inf-reset", "inf-reset-str", "inf-schema",
        "inf-minutes", "deep-nesting"])
def test_an_odd_value_never_takes_the_other_providers_down(tmp_path, bad):
    model = _all(tmp_path, {"claude": GOOD, "codex": bad})
    by_id = {p["id"]: p for p in model["all"]}
    assert by_id["anthropic"]["status"] == "ready"
    assert [m["percent"] for m in by_id["anthropic"]["metrics"]] == [40, 20]
    for metric in by_id["openai"]["metrics"]:
        assert metric["percent"] is None or 0 <= metric["percent"] <= 100


def test_non_string_labels_never_show_a_python_repr(tmp_path):
    model = _all(tmp_path, {"codex": {
        "schemaVersion": 3, "_plan": {"a": 1}, "_source": "x",
        "buckets": [
            {"id": "codex", "isGeneral": True,
             "windows": [{"minutes": 90, "label": ["x"], "utilization": 0.1, "reset": True}]},
            {"id": {"b": 2}, "label": 7, "isGeneral": False,
             "windows": [{"minutes": 300, "utilization": 0.2, "reset": RESET}]}]}})
    (p,) = model["all"]
    assert p["plan"] == ""
    assert [m["label"] for m in p["metrics"]] == ["90m", "Session (5h)"]
    assert p["metrics"][0]["reset_at"] is None


def test_stale_flag_and_future_clock_are_not_fresh(tmp_path):
    import os
    import time
    model = _all(tmp_path, {"claude": dict(GOOD, _stale=True), "codex": GOOD})
    assert {p["id"]: p["stale"] for p in model["all"]} == {
        "anthropic": True, "openai": False}
    future = time.time() + 3600
    os.utime(tmp_path / "codex-usage.json", (future, future))
    model = _all(tmp_path, {})
    assert {p["id"]: p["stale"] for p in model["all"]}["openai"] is True


@pytest.mark.parametrize("order", ["highest", "lowest"])
def test_an_estimate_ranks_after_every_real_quota(tmp_path, order):
    full = {"5h-utilization": "1.0000", "5h-reset": "0",
            "7d-utilization": "0.0000", "7d-reset": "0", "_source": "storage"}
    model = _all(tmp_path, {"claude": GOOD, "codex": GOOD, "opencode": full},
                 "--order", order)
    assert [p["id"] for p in model["all"]][-1] == "opencode"
    assert model["primary"]["id"] != "opencode"
