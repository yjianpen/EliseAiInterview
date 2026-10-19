import os
import tempfile
import unittest

import index

XML = """<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/">
  <page><title>Aethermist Valley</title><ns>0</ns><id>1</id><revision><text>
  {{Infobox valley | population = 3,000}}
  The '''Norathi''' call it ''Skyfather's Breath''.&lt;ref&gt;Src&lt;/ref&gt;
  Home of the [[Luminous Tree Frog|frog]] &amp;ndash; see [[Lunar Cartography Expedition of 1689#Launch]].
  </text></revision></page>
  <page><title>Luminous Tree Frog</title><ns>0</ns><id>2</id><revision><text>A frog.</text></revision></page>
  <page><title>AethermistValley</title><ns>0</ns><id>3</id><redirect title="Aethermist Valley"/>
  <revision><text>#REDIRECT [[Aethermist Valley]]</text></revision></page>
</mediawiki>"""


class IndexTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "mini.xml")
        with open(self.path, "w") as f:
            f.write(XML)
        index._CACHE.clear()

    def tearDown(self):
        self.dir.cleanup()

    def test_clean_wikitext(self):
        out = index.clean_wikitext("'''Bold''' [[A|b]] [[C#D]] &amp;ndash; x<ref>r</ref><!-- c -->")
        self.assertEqual(out, "Bold b C – x")

    def test_load_pages(self):
        idx = index.load_pages(self.path)
        text = idx["pages"]["Aethermist Valley"]
        self.assertIn("Norathi call it Skyfather's Breath.", text)
        self.assertIn("population = 3,000", text)  # infobox facts are kept
        self.assertNotIn("Src", text)
        self.assertNotIn("AethermistValley", idx["pages"])  # redirects are not articles
        self.assertEqual(idx["aliases"]["aethermistvalley"], "Aethermist Valley")
        self.assertEqual(idx["links"]["Aethermist Valley"],
                         ["Luminous Tree Frog", "Lunar Cartography Expedition of 1689"])

    def test_docs_map_rows_to_xml_lines(self):
        xml = XML.replace("<id>1</id><revision><text>", "<id>7183942</id><revision><text>Lead<ref>multi\nline</ref>\n")
        with open(self.path, "w") as f:
            f.write(xml)
        idx = index.load_pages(self.path)
        page_id, start = idx["docs"]["Aethermist Valley"]
        self.assertEqual(page_id, 7183942)
        with open(self.path) as f:
            xml_lines = f.read().split("\n")
        for row, text in enumerate(idx["pages"]["Aethermist Valley"].split("\n")):
            if text:  # every non-empty cleaned row comes from XML line start + row (1-based)
                self.assertIn(text.split()[0].strip(".'"), xml_lines[start + row - 1], row)
        frog_id, frog_line = idx["docs"]["Luminous Tree Frog"]
        self.assertEqual(frog_id, 2)
        self.assertIn("<text>A frog.</text>", xml_lines[frog_line - 1])
        self.assertNotIn("AethermistValley", idx["docs"])

    def test_get_index_caches(self):
        first = index.get_index(self.path)
        self.assertIs(index.get_index(self.path), first)  # in-memory cache
        self.assertTrue(os.path.exists(self.path + ".v2.idx.pkl"))
        index._CACHE.clear()
        self.assertEqual(index.get_index(self.path), first)  # reloaded from pickle


if __name__ == "__main__":
    unittest.main()
