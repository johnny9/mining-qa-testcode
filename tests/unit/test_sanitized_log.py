from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from miner_testcode.redaction import publish_sanitized_log


class SanitizedLogTest(unittest.TestCase):
    def test_raw_log_stays_private_and_public_log_is_digest_addressed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private = root / ".private" / "run" / "runner.raw.log"
            private.parent.mkdir(parents=True)
            private.write_text(
                "device-canary-east password=secret /private/canary/path\n",
                encoding="utf-8",
            )
            public = root / "run"
            public.mkdir()
            descriptor = publish_sanitized_log(
                private,
                public,
                project_root=root,
                replacements={
                    "device-canary-east": "<redacted-canary>",
                    "/private/canary/path": "<redacted-canary>",
                },
            )
            published = (public / str(descriptor["path"])).read_bytes()
            self.assertEqual(descriptor["sha256"], __import__("hashlib").sha256(published).hexdigest())
            self.assertNotIn(b"device-canary-east", published)
            self.assertNotIn(b"/private/canary/path", published)
            self.assertNotIn(b"password=secret", published)
            self.assertIn(b"password=<redacted>", published)
            self.assertIn("device-canary-east", private.read_text(encoding="utf-8"))
            self.assertEqual(
                json.loads((public / "sanitized-log.json").read_text(encoding="utf-8")),
                descriptor,
            )

    def test_independent_scan_rejects_unredacted_private_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "raw.log"
            raw.write_text("private-token", encoding="utf-8")
            public = root / "public"
            public.mkdir()
            with self.assertRaisesRegex(ValueError, "private replacement key"):
                publish_sanitized_log(
                    raw,
                    public,
                    project_root=root,
                    replacements={"private-token": "private-token"},
                )


if __name__ == "__main__":
    unittest.main()
