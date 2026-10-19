import os
import tempfile
import unittest

import index
import search

# Mirrors the real dump: the expedition article names a different launch site, and only the
# valley article claims the expedition launched from it, so the hop needs a backlink search.
XML = """<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/">
  <page><title>Lunar Cartography Expedition of 1689</title><revision><text>
  The expedition was a 1689 balloon flight launched from [[Starrise]].</text></revision></page>
  <page><title>Aethermist Valley</title><revision><text>The Norathi call it Skyfather's Breath.
  The Lunar Cartography Expedition launched here. The [[Luminous Tree Frog]] is endemic.</text></revision></page>
  <page><title>Luminous Tree Frog</title><revision><text>
  Current population estimates suggest fewer than 3,000 individuals remain.</text></revision></page>
  <page><title>Starrise</title><revision><text>A village in Yorkshire.</text></revision></page>
  <page><title>AethermistValley</title><redirect title="Aethermist Valley"/><revision><text>#REDIRECT</text></revision></page>
</mediawiki>"""


class SearchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "mini.xml")
            with open(path, "w") as f:
                f.write(XML)
            cls.idx = index.load_pages(path)

    def test_search_ranks_by_bm25(self):
        hits = search.search(self.idx, "What do the Norathi people call the valley?")
        self.assertEqual(hits[0][0], "Aethermist Valley")
        self.assertIn("Skyfather's Breath", hits[0][1])
        self.assertEqual(search.search(self.idx, "zzz unknown words"), [])

    def test_read_article_resolves_loose_titles(self):
        for loose in ["Lunar Cartography Expedition", "aethermistvalley", "Luminous Tree Frgo"]:
            self.assertFalse(search.read_article(self.idx, loose).startswith("No article"), loose)
        out = search.read_article(self.idx, "aethermist valley")
        self.assertTrue(out.startswith("# Aethermist Valley\n"))
        self.assertTrue(out.endswith("Links to: Luminous Tree Frog"))
        self.assertEqual(search.read_article(self.idx, "Atlantis"), "No article found for 'Atlantis'.")

    def test_find_mentions_finds_backlinks(self):
        hits = search.find_mentions(self.idx, "lunar cartography expedition")
        self.assertIn("Aethermist Valley", [t for t, _ in hits])
        self.assertIn("launched here", dict(hits)["Aethermist Valley"])
        self.assertEqual(search.find_mentions(self.idx, "Atlantis"), [])


if __name__ == "__main__":
    unittest.main()
