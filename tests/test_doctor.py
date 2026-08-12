from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "skills" / "vision-beyond" / "scripts" / "doctor.py"
SPEC = importlib.util.spec_from_file_location("vision_beyond_doctor", SCRIPT)
doctor = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(doctor)


class DoctorTests(unittest.TestCase):
    def test_identity_is_redacted(self) -> None:
        payload = {
            "verified": True,
            "identities": {
                "user": {
                    "available": True,
                    "verified": True,
                    "tokenStatus": "valid",
                    "openId": "sensitive-user-id",
                    "userName": "Sensitive Name",
                    "scope": "search:message im:message:readonly search:docs:read",
                }
            },
        }
        result = doctor.inspect_auth(payload)
        rendered = repr(result)
        self.assertNotIn("sensitive-user-id", rendered)
        self.assertNotIn("Sensitive Name", rendered)
        self.assertTrue(result["ready_for_core_scan"])

    def test_reaction_capability_is_separate(self) -> None:
        result = doctor.evaluate_capabilities({"search:message", "im:message:readonly", "search:docs:read"})
        self.assertTrue(result["messages_search"]["available"])
        self.assertFalse(result["message_reactions"]["available"])

    def test_document_statistics_accepts_any_read_scope(self) -> None:
        for scope in ("drive:drive.metadata:readonly", "drive:drive:readonly", "drive:drive"):
            with self.subTest(scope=scope):
                result = doctor.evaluate_capabilities({scope})
                self.assertTrue(result["document_statistics"]["available"])

    def test_one_read_source_can_run_in_degraded_mode(self) -> None:
        payload = {
            "verified": True,
            "identities": {
                "user": {
                    "available": True,
                    "verified": True,
                    "tokenStatus": "valid",
                    "scope": "approval:task:read",
                }
            },
        }
        result = doctor.inspect_auth(payload)
        self.assertTrue(result["ready_for_core_scan"])
        self.assertEqual(result["available_sources"], ["approval_tasks"])

    def test_contact_probe_can_enable_read_only_mode_without_scope_inventory(self) -> None:
        result = doctor.inspect_compat_probe({
            "ok": True,
            "method": "contact_self",
            "identity_assurance": "resolved",
            "warnings": ["auth status is unavailable in this CLI build; using read-only compatibility probes"],
        })
        self.assertTrue(result["ready_for_core_scan"])
        self.assertFalse(result["user_identity"]["verified"])
        self.assertEqual(result["available_sources"], [])
        self.assertFalse(result["capabilities"]["messages_search"]["available"])

    def test_task_canary_only_confirms_tasks(self) -> None:
        result = doctor.inspect_compat_probe({
            "ok": True,
            "method": "task_canary",
            "identity_assurance": "user_context",
            "warnings": ["task canary proves user-context access, not the user's stable subject identity"],
        })
        self.assertTrue(result["ready_for_core_scan"])
        self.assertEqual(result["available_sources"], ["tasks"])
        self.assertTrue(result["capabilities"]["tasks"]["available"])
        self.assertFalse(result["capabilities"]["messages_search"]["available"])


if __name__ == "__main__":
    unittest.main()
