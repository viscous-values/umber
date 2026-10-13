"""scripts/register_vscode_extension.py: the extensions.json entry VSCode needs
before it will load a symlinked extension.

Run: python3 -m unittest discover -s tests
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import register_vscode_extension as reg  # noqa: E402

OTHER = {"identifier": {"id": "someone.else"}, "version": "3.2.1", "relativeLocation": "someone.else-3.2.1"}


class RegisterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.json = self.dir / "extensions.json"

    def tearDown(self):
        self.tmp.cleanup()

    def _umber(self):
        return [e for e in json.loads(self.json.read_text()) if e["identifier"]["id"] == "viscous-values.umber"]

    def test_creates_the_file_with_one_entry(self):
        reg.register(self.dir, "2.0.0")
        (entry,) = self._umber()
        self.assertEqual(entry["version"], "2.0.0")
        self.assertEqual(entry["relativeLocation"], "viscous-values.umber-2.0.0")
        self.assertEqual(entry["location"]["path"], str(self.dir / "viscous-values.umber-2.0.0"))

    def test_upgrades_an_older_entry_and_keeps_other_extensions(self):
        old = {"identifier": {"id": "viscous-values.umber"}, "version": "1.1.1",
               "relativeLocation": "viscous-values.umber-1.1.1"}
        self.json.write_text(json.dumps([OTHER, old]))
        reg.register(self.dir, "2.0.0")
        data = json.loads(self.json.read_text())
        self.assertIn(OTHER, data)
        (entry,) = self._umber()
        self.assertEqual(entry["version"], "2.0.0")

    def test_malformed_file_is_left_alone(self):
        self.json.write_text("{not json")
        with self.assertRaises(SystemExit):
            reg.register(self.dir, "2.0.0")
        self.assertEqual(self.json.read_text(), "{not json")


if __name__ == "__main__":
    unittest.main()
