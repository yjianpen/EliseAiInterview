import io
import os
import sys
from contextlib import redirect_stdout
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import candidate_solution
import index
import react_loop
from test_react_loop import FakeClient

PAGE = '<page><title>{}</title><ns>0</ns><revision><text>{}</text></revision></page>'
MINI_XML = '<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/">' + "".join([
    PAGE.format("Lunar Cartography Expedition of 1689", "It launched from the [[Aethermist Valley]]."),
    PAGE.format("Aethermist Valley", "The Norathi call it Skyfather's Breath. "
                "The [[Luminous Tree Frog]] is endemic to this valley."),
    PAGE.format("Luminous Tree Frog", "Fewer than 3,000 individuals remain in the wild."),
    '<page><title>Ignored Redirect</title><redirect title="Aethermist Valley"/>'
    '<revision><text>#REDIRECT</text></revision></page>']) + "</mediawiki>"
HARD_Q = ("What is the current population estimate of the species that is endemic to the "
          "valley from which the Lunar Cartography Expedition was launched?")


def titles(corpus, question):
    return [title for title, _ in candidate_solution.retrieve(question, corpus)]


class RetrieveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        cls.path = os.path.join(cls.dir.name, "mini.xml")
        with open(cls.path, "w", encoding="utf-8") as fh:
            fh.write(MINI_XML)
        cls.corpus = index.load_pages(cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_retrieve_follows_links_for_multi_hop(self):
        self.assertIn("Aethermist Valley", titles(self.corpus, "What do the Norathi call the Aethermist Valley?"))
        for title in ["Lunar Cartography Expedition of 1689", "Aethermist Valley", "Luminous Tree Frog"]:
            self.assertIn(title, titles(self.corpus, HARD_Q))

    def test_fallback_answer_sends_retrieved_articles(self):
        client = FakeClient([(" Skyfather's Breath ", None)])
        reply = candidate_solution.fallback_answer("What do the Norathi call it?", self.path, client=client)
        self.assertEqual(reply, "Skyfather's Breath")
        self.assertIn("Title: Aethermist Valley", client.requests[0]["messages"][1]["content"])


class AnswerFallbackTests(unittest.TestCase):
    def setUp(self):
        self.saved = react_loop.react_loop, candidate_solution.fallback_answer

    def tearDown(self):
        react_loop.react_loop, candidate_solution.fallback_answer = self.saved

    def test_fallback_runs_only_when_react_loop_fails(self):
        candidate_solution.fallback_answer = lambda q, f: "from fallback"
        react_loop.react_loop = lambda q, f, with_refs: ("I don't know", [])  # a refusal is final
        self.assertEqual(candidate_solution.answer("Q?", "x.xml"), "I don't know")
        react_loop.react_loop = lambda q, f, with_refs: 1 / 0
        self.assertEqual(candidate_solution.answer("Q?", "x.xml"), "from fallback")
        candidate_solution.fallback_answer = lambda q, f: 1 / 0
        self.assertEqual(candidate_solution.answer("Q?", "x.xml"), "I don't know")  # never raises

    def test_answer_prints_references_but_returns_clean_answer(self):
        ref = {"page_id": 7183942, "xml_line": 4685499, "title": "Aethermist Valley", "text": "Skyfather's Breath"}
        react_loop.react_loop = lambda q, f, with_refs: ("Skyfather's Breath", [ref])
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(candidate_solution.answer("Q?", "x.xml"), "Skyfather's Breath")
        self.assertEqual(out.getvalue(), "References for: Q?\n"
                         "  [7183942:4685499] Aethermist Valley | Skyfather's Breath\n")
        self.assertIn("(none)", candidate_solution.format_references("Q?", []))


if __name__ == "__main__":
    unittest.main()
