from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKIP = {Path(__file__).resolve()}
PATTERNS = {
    "feishu_app_id": re.compile(r"\bcli_[A-Za-z0-9_-]{8,}\b"),
    "feishu_object_id": re.compile(r"\b(?:ou|oc|om|omt)_[A-Za-z0-9_-]{8,}\b"),
    "github_token": re.compile(r"\bgh[opsu]_[A-Za-z0-9]{20,}\b"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "local_home_path": re.compile(r"/Users/[^/\s]+/"),
}


class PublicSafetyTests(unittest.TestCase):
    def test_no_live_credentials_or_object_ids(self) -> None:
        findings: list[str] = []
        for path in ROOT.rglob("*"):
            if (
                not path.is_file()
                or ".git" in path.parts
                or ".agents" in path.parts
                or path.name == "skills-lock.json"
                or path.resolve() in SKIP
            ):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for label, pattern in PATTERNS.items():
                if pattern.search(text):
                    findings.append(f"{path.relative_to(ROOT)}:{label}")
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
