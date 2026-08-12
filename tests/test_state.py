from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "skills" / "vision-beyond" / "scripts" / "state.py"
SPEC = importlib.util.spec_from_file_location("vision_beyond_state", SCRIPT)
state_module = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(state_module)


class StateTests(unittest.TestCase):
    def test_initial_state_is_valid(self) -> None:
        state = state_module.initial_state("17:30", "Asia/Shanghai")
        state_module.validate_state(state)

    def test_raw_identifiers_are_rejected(self) -> None:
        state = state_module.initial_state("09:00", "UTC")
        state["profile"]["topics"] = ["ou_" + "1234567890"]
        with self.assertRaises(state_module.StateError):
            state_module.validate_state(state)

    def test_atomic_write_uses_private_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private" / "state.json"
            state_module.atomic_write(path, state_module.initial_state("09:00", "UTC"))
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["scan"]["baseline_days"], 7)

    def test_last_success_requires_timezone(self) -> None:
        state = state_module.initial_state("09:00", "UTC")
        state["scan"]["last_success_at"] = "2026-08-12T09:00:00"
        with self.assertRaises(state_module.StateError):
            state_module.validate_state(state)

    def test_success_checkpoint_cannot_move_backwards(self) -> None:
        with self.assertRaises(state_module.StateError):
            state_module.validate_checkpoint(
                "2026-08-12T09:00:00+00:00",
                "2026-08-11T09:00:00+00:00",
            )


if __name__ == "__main__":
    unittest.main()
