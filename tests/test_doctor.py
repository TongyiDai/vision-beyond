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


if __name__ == "__main__":
    unittest.main()
