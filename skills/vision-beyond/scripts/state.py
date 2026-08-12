#!/usr/bin/env python3
"""Create and validate privacy-minimal state for vision-beyond."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SCHEMA_VERSION = 1
MAX_FINGERPRINTS = 2000
TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
SOURCE_RE = re.compile(r"^[a-z][a-z0-9_-]{1,20}$")
FINGERPRINT_RE = re.compile(r"^[a-z][a-z0-9_-]{1,20}:[0-9a-f]{64}$")
SENSITIVE_VALUE_RE = re.compile(
    r"(?:https?://|\b(?:access[_-]?token|device[_-]?code)\b|\b(?:ou|oc|om|omt|cli)_[A-Za-z0-9_-]{8,})",
    re.IGNORECASE,
)


class StateError(ValueError):
    pass


def default_path() -> Path:
    configured = os.environ.get("VISION_BEYOND_STATE_PATH")
    return Path(configured).expanduser() if configured else Path.home() / ".codex" / "vision-beyond" / "state.json"


def parse_rfc3339(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StateError(f"invalid RFC3339 timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise StateError("timestamp must include a timezone offset")
    return parsed


def validate_checkpoint(previous: str | None, current: str) -> None:
    if previous and parse_rfc3339(current) < parse_rfc3339(previous):
        raise StateError("last_success_at cannot move backwards")


def ensure_timezone(value: str) -> ZoneInfo:
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise StateError(f"unknown IANA timezone: {value}") from exc


def initial_state(report_time: str, timezone: str) -> dict[str, Any]:
    if not TIME_RE.match(report_time):
        raise StateError("report_time must use HH:MM")
    ensure_timezone(timezone)
    return {
        "schema_version": SCHEMA_VERSION,
        "schedule": {"report_time": report_time, "timezone": timezone},
        "profile": {
            "confirmed": False,
            "topics": [],
            "exclude_terms": [],
            "source_preferences": {},
        },
        "scan": {"baseline_days": 7, "last_success_at": None, "fingerprints": []},
    }


def reject_sensitive_values(value: Any, path: str = "state") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            reject_sensitive_values(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_sensitive_values(child, f"{path}[{index}]")
    elif isinstance(value, str) and SENSITIVE_VALUE_RE.search(value):
        raise StateError(f"sensitive or raw identifier found at {path}")


def validate_state(state: dict[str, Any]) -> None:
    if state.get("schema_version") != SCHEMA_VERSION:
        raise StateError(f"schema_version must be {SCHEMA_VERSION}")
    schedule = state.get("schedule")
    profile = state.get("profile")
    scan = state.get("scan")
    if not isinstance(schedule, dict) or not TIME_RE.match(str(schedule.get("report_time", ""))):
        raise StateError("schedule.report_time must use HH:MM")
    ensure_timezone(str(schedule.get("timezone", "")))
    if not isinstance(profile, dict) or not isinstance(profile.get("confirmed"), bool):
        raise StateError("profile.confirmed must be boolean")
    for key in ("topics", "exclude_terms"):
        values = profile.get(key)
        if not isinstance(values, list) or not all(isinstance(item, str) and item.strip() for item in values):
            raise StateError(f"profile.{key} must be an array of non-empty strings")
    if not isinstance(profile.get("source_preferences"), dict):
        raise StateError("profile.source_preferences must be an object")
    if not isinstance(scan, dict) or scan.get("baseline_days") != 7:
        raise StateError("scan.baseline_days must be 7")
    last_success = scan.get("last_success_at")
    if last_success is not None:
        parse_rfc3339(str(last_success))
    fingerprints = scan.get("fingerprints")
    if not isinstance(fingerprints, list) or len(fingerprints) > MAX_FINGERPRINTS:
        raise StateError(f"scan.fingerprints must contain at most {MAX_FINGERPRINTS} items")
    if not all(isinstance(item, str) and FINGERPRINT_RE.match(item) for item in fingerprints):
        raise StateError("scan.fingerprints contains an invalid value")
    reject_sensitive_values(state)


def load_state(path: Path) -> dict[str, Any]:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StateError(f"state file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise StateError(f"state file is invalid JSON: {path}") from exc
    if not isinstance(state, dict):
        raise StateError("state root must be an object")
    validate_state(state)
    return state


def atomic_write(path: Path, state: dict[str, Any]) -> None:
    validate_state(state)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, stat.S_IRWXU)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=".state-", suffix=".json", delete=False
    ) as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temp_path = Path(handle.name)
    os.chmod(temp_path, stat.S_IRUSR | stat.S_IWUSR)
    os.replace(temp_path, path)


def command_init(args: argparse.Namespace) -> int:
    path = args.path
    if path.exists() and not args.force:
        load_state(path)
        print(json.dumps({"ok": True, "created": False, "path": str(path)}, ensure_ascii=False))
        return 0
    atomic_write(path, initial_state(args.report_time, args.timezone))
    print(json.dumps({"ok": True, "created": True, "path": str(path)}, ensure_ascii=False))
    return 0


def command_validate(args: argparse.Namespace) -> int:
    load_state(args.path)
    mode = stat.S_IMODE(args.path.stat().st_mode)
    print(json.dumps({"ok": True, "schema_version": SCHEMA_VERSION, "private_mode": mode == 0o600}))
    return 0


def command_fingerprint(args: argparse.Namespace) -> int:
    if not SOURCE_RE.match(args.source):
        raise StateError("source must use lowercase letters, digits, underscore, or hyphen")
    raw = sys.stdin.buffer.read()
    if not raw:
        raise StateError("fingerprint input is empty")
    print(f"{args.source}:{hashlib.sha256(raw).hexdigest()}")
    return 0


def command_window(args: argparse.Namespace) -> int:
    state = load_state(args.path)
    timezone = ensure_timezone(state["schedule"]["timezone"])
    end = parse_rfc3339(args.at).astimezone(timezone) if args.at else datetime.now(timezone)
    last_success = state["scan"]["last_success_at"]
    if last_success:
        start = parse_rfc3339(last_success).astimezone(timezone)
        baseline = False
    else:
        start = end - timedelta(days=state["scan"]["baseline_days"])
        baseline = True
    if end < start:
        raise StateError("window end cannot be earlier than the last successful scan")
    print(
        json.dumps(
            {"ok": True, "baseline": baseline, "start": start.isoformat(), "end": end.isoformat()},
            ensure_ascii=False,
        )
    )
    return 0


def command_mark_success(args: argparse.Namespace) -> int:
    state = load_state(args.path)
    success_at = parse_rfc3339(args.at).isoformat()
    previous = state["scan"]["last_success_at"]
    validate_checkpoint(previous, success_at)
    incoming = [line.strip() for line in sys.stdin if line.strip()]
    if not all(FINGERPRINT_RE.match(item) for item in incoming):
        raise StateError("stdin contains a raw or invalid fingerprint")
    prior = state["scan"]["fingerprints"]
    state["scan"]["fingerprints"] = list(dict.fromkeys(prior + incoming))[-MAX_FINGERPRINTS:]
    state["scan"]["last_success_at"] = success_at
    atomic_write(args.path, state)
    print(json.dumps({"ok": True, "stored_fingerprints": len(state["scan"]["fingerprints"])}))
    return 0


def command_set_profile(args: argparse.Namespace) -> int:
    state = load_state(args.path)
    topics = list(dict.fromkeys(state["profile"]["topics"] + args.topic))
    excludes = list(dict.fromkeys(state["profile"]["exclude_terms"] + args.exclude))
    state["profile"]["topics"] = topics
    state["profile"]["exclude_terms"] = excludes
    if args.confirm:
        if not topics:
            raise StateError("at least one topic is required before confirmation")
        state["profile"]["confirmed"] = True
    atomic_write(args.path, state)
    print(json.dumps({"ok": True, "confirmed": state["profile"]["confirmed"], "topics": len(topics)}))
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--path", type=Path, default=default_path())
    commands = root.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init")
    init.add_argument("--report-time", required=True)
    init.add_argument("--timezone", required=True)
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=command_init)

    validate = commands.add_parser("validate")
    validate.set_defaults(func=command_validate)

    fingerprint = commands.add_parser("fingerprint")
    fingerprint.add_argument("--source", required=True)
    fingerprint.set_defaults(func=command_fingerprint)

    window = commands.add_parser("window")
    window.add_argument("--at", help="RFC3339 end time, defaults to now")
    window.set_defaults(func=command_window)

    success = commands.add_parser("mark-success")
    success.add_argument("--at", required=True)
    success.set_defaults(func=command_mark_success)

    profile = commands.add_parser("set-profile")
    profile.add_argument("--topic", action="append", default=[])
    profile.add_argument("--exclude", action="append", default=[])
    profile.add_argument("--confirm", action="store_true")
    profile.set_defaults(func=command_set_profile)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        return args.func(args)
    except (OSError, StateError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
