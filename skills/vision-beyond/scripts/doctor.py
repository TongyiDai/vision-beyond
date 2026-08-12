#!/usr/bin/env python3
"""Read-only readiness check for the vision-beyond skill."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lark_identity_probe import probe_lark_identity, public_probe


class Capability:
    def __init__(
        self,
        level: str,
        all_of: tuple[str, ...] = (),
        any_of: tuple[str, ...] = (),
    ) -> None:
        self.level = level
        self.all_of = all_of
        self.any_of = any_of


CAPABILITIES = {
    "messages_search": Capability("core", all_of=("search:message", "im:message:readonly")),
    "message_context": Capability(
        "recommended",
        all_of=("im:message.group_msg:get_as_user", "im:message.p2p_msg:get_as_user"),
    ),
    "message_reactions": Capability("recommended", all_of=("im:message.reactions:read",)),
    "documents_search": Capability("core", all_of=("search:docs:read",)),
    "document_statistics": Capability(
        "recommended",
        any_of=("drive:drive.metadata:readonly", "drive:drive:readonly", "drive:drive"),
    ),
    "document_open_record": Capability("recommended", all_of=("drive:file:view_record:readonly",)),
    "document_content": Capability(
        "recommended",
        any_of=("docs:document.content:read", "docx:document:readonly"),
    ),
    "calendar": Capability("optional", all_of=("calendar:calendar.event:read",)),
    "meetings": Capability("optional", all_of=("vc:meeting.search:read",)),
    "meeting_notes": Capability("optional", all_of=("vc:note:read",)),
    "minutes": Capability(
        "optional",
        all_of=("minutes:minutes.search:read", "minutes:minutes.artifacts:read"),
    ),
    "tasks": Capability("optional", all_of=("task:task:read",)),
    "approval_tasks": Capability("optional", all_of=("approval:task:read",)),
    "approval_instances": Capability("optional", all_of=("approval:instance:read",)),
    "okr": Capability("recommended", all_of=("okr:okr.period:readonly",)),
}


def parse_version(output: str) -> str | None:
    match = re.search(r"\b(\d+\.\d+\.\d+)\b", output)
    return match.group(1) if match else None


def evaluate_capabilities(scopes: set[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name, requirement in CAPABILITIES.items():
        missing = [scope for scope in requirement.all_of if scope not in scopes]
        any_ok = not requirement.any_of or any(scope in scopes for scope in requirement.any_of)
        if not any_ok:
            missing.append("one_of:" + "|".join(requirement.any_of))
        result[name] = {
            "available": not missing,
            "level": requirement.level,
            "missing": missing,
        }
    return result


def unknown_capabilities(reason: str, *, available: set[str] | None = None) -> dict[str, dict[str, Any]]:
    available = available or set()
    result: dict[str, dict[str, Any]] = {}
    for name, requirement in CAPABILITIES.items():
        result[name] = {
            "available": name in available,
            "level": requirement.level,
            "missing": [] if name in available else [reason],
        }
    return result


def inspect_auth(payload: dict[str, Any]) -> dict[str, Any]:
    identities = payload.get("identities") if isinstance(payload.get("identities"), dict) else {}
    user = identities.get("user") if isinstance(identities.get("user"), dict) else {}
    scopes = set(str(user.get("scope", "")).split())
    capabilities = evaluate_capabilities(scopes)
    verified = bool(payload.get("verified")) and bool(user.get("verified"))
    source_names = (
        "messages_search",
        "documents_search",
        "calendar",
        "meetings",
        "tasks",
        "approval_tasks",
    )
    available_sources = [name for name in source_names if capabilities[name]["available"]]
    ready_core = verified and bool(available_sources)
    return {
        "user_identity": {
            "available": bool(user.get("available")),
            "verified": verified,
            "token_status": user.get("tokenStatus") if user.get("tokenStatus") in {"valid", "expired"} else "unknown",
        },
        "capabilities": capabilities,
        "available_sources": available_sources,
        "ready_for_core_scan": ready_core,
        "ready_for_full_scan": ready_core and all(item["available"] for item in capabilities.values()),
    }


def inspect_compat_probe(probe: dict[str, Any]) -> dict[str, Any]:
    warnings = list(probe.get("warnings") or [])
    assurance = probe.get("identity_assurance")
    if assurance == "resolved":
        warnings.append("scope inventory is unavailable in this lark-cli runtime; probe each source live during scan")
        return {
            "probe": public_probe(probe),
            "user_identity": {"available": True, "verified": False, "token_status": "unknown"},
            "capabilities": unknown_capabilities("scope inventory unavailable"),
            "available_sources": [],
            "ready_for_core_scan": True,
            "ready_for_full_scan": False,
            "warnings": warnings,
        }
    if assurance == "user_context":
        warnings.append("stable subject identity remains unresolved; do not use this mode for subject-bound writes or bindings")
        return {
            "probe": public_probe(probe),
            "user_identity": {"available": True, "verified": False, "token_status": "unknown"},
            "capabilities": unknown_capabilities("scope inventory unavailable", available={"tasks"}),
            "available_sources": ["tasks"],
            "ready_for_core_scan": True,
            "ready_for_full_scan": False,
            "warnings": warnings,
        }
    return {
        "probe": public_probe(probe),
        "user_identity": {"available": False, "verified": False, "token_status": "unknown"},
        "capabilities": unknown_capabilities("identity probe unavailable"),
        "available_sources": [],
        "ready_for_core_scan": False,
        "ready_for_full_scan": False,
        "warnings": warnings,
    }


def main() -> int:
    cli = shutil.which("lark-cli")
    result: dict[str, Any] = {
        "ok": False,
        "lark_cli": {"installed": bool(cli), "version": None},
        "probe": None,
        "user_identity": {"available": False, "verified": False, "token_status": "unknown"},
        "capabilities": {},
        "available_sources": [],
        "ready_for_core_scan": False,
        "ready_for_full_scan": False,
        "warnings": [],
    }
    if not cli:
        result["warnings"].append("lark-cli is not installed")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    env = os.environ.copy()
    env["LARKSUITE_CLI_NO_UPDATE_NOTIFIER"] = "1"
    env["LARKSUITE_CLI_NO_SKILLS_NOTIFIER"] = "1"
    try:
        version_run = subprocess.run(
            [cli, "--version"], capture_output=True, text=True, timeout=10, env=env, check=False
        )
        result["lark_cli"]["version"] = parse_version(version_run.stdout + version_run.stderr)
    except (OSError, subprocess.TimeoutExpired):
        result["warnings"].append("lark-cli readiness check failed or timed out")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    probe = probe_lark_identity(env=env)
    result["probe"] = public_probe(probe)
    if not probe["ok"]:
        result["warnings"].extend(probe.get("warnings") or [])
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    if probe["method"] != "auth_status":
        result.update(inspect_compat_probe(probe))
        result["ok"] = result["ready_for_core_scan"]
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1

    try:
        auth_run = subprocess.run(
            [cli, "auth", "status", "--json", "--verify"],
            capture_output=True,
            text=True,
            timeout=25,
            env=env,
            check=False,
        )
        auth_payload = json.loads(auth_run.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        result.update(inspect_compat_probe(probe))
        result["warnings"].append("lark-cli returned an unreadable authentication response")
        result["ok"] = result["ready_for_core_scan"]
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1

    result.update(inspect_auth(auth_payload))
    result["probe"] = public_probe(probe)
    result["ok"] = result["ready_for_core_scan"]
    if not result["ready_for_full_scan"]:
        result["warnings"].append("some recommended or optional sources will run in degraded mode")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
