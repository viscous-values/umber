"""render_previews.py: content drawn into the shipped Plasma theme previews.

Run: python3 -m unittest discover -s tests
"""

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import palette_lib  # noqa: E402
import render_previews  # noqa: E402

SHIPPED = [REPO / "palette.toml", *sorted((REPO / "palettes").glob("*.toml"))]


class ConceptBlurbTest(unittest.TestCase):
    def test_desktop_preview_carries_the_whole_concept_line(self):
        for path in SHIPPED:
            with self.subTest(variant=path.name):
                pal = palette_lib.prepare(path)
                headline, lines = render_previews.concept_blurb(pal)
                sentences = pal["meta"]["concept"].split(". ")
                self.assertEqual(headline, sentences[0])
                self.assertEqual(" ".join(lines), sentences[1].rstrip(".") + ".")


if __name__ == "__main__":
    unittest.main()
