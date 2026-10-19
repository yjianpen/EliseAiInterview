import json
import os
import tempfile
import unittest
from types import SimpleNamespace as NS

import react_loop
from test_search import XML  # expedition / valley / frog fixture shaped like the real dump


def tool_call(i, name, arg):
    return NS(id=f"call{i}", function=NS(name=name, arguments=json.dumps(arg)))


class FakeClient:
    """Replays scripted model turns and records every request it receives."""
    def __init__(self, turns):
        self.turns, self.requests = list(turns), []
        self.chat = NS(completions=NS(create=self.create))

    def create(self, **kwargs):
        self.requests.append(kwargs)
        content, calls = self.turns.pop(0)
        return NS(choices=[NS(message=NS(content=content, tool_calls=calls))])


class ReactLoopTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "mini.xml")
        with open(self.path, "w") as f:
            f.write(XML)

    def tearDown(self):
        self.dir.cleanup()

    def test_multi_hop_feeds_observations_back(self):
        client = FakeClient([
            ("Hop 1: which valley launched the expedition?",
             [tool_call(1, "find_mentions", {"phrase": "Lunar Cartography Expedition"})]),
            (None, [tool_call(2, "read_article", {"title": "luminous tree frog"})]),
            ("3,000", None)])
        q = "Population of the species endemic to the valley the Lunar Cartography Expedition launched from?"
        self.assertEqual(react_loop.react_loop(q, self.path, client=client), "3,000")
        tool_msgs = [m for m in client.requests[-1]["messages"] if m["role"] == "tool"]
        self.assertIn("Aethermist Valley", tool_msgs[0]["content"])  # backlink found the valley
        self.assertIn("fewer than 3,000", tool_msgs[1]["content"])

    def test_refusals_keep_agent_wording(self):
        graceful = "I don't know - no article states the balloon's name."
        for reply, expected in [(graceful, graceful), ("", "I don't know"), (None, "I don't know"),
                                ('"Skyfather\'s Breath."', "Skyfather's Breath."),  # one wrapping pair only
                                ('call it "Skyfather\'s Breath."', 'call it "Skyfather\'s Breath."')]:
            client = FakeClient([(reply, None)])
            self.assertEqual(react_loop.react_loop("Q?", self.path, client=client), expected)

    def test_tool_failures_are_passed_to_the_agent(self):
        client = FakeClient([(None, [NS(id="c1", function=NS(name="search", arguments="{not json"))]),
                             (None, [tool_call(2, "read_article", {"title": "Atlantis"})]),
                             (None, [tool_call(3, "find_mentions", {"phrase": "Atlantis"})]),
                             ("I don't know - nothing mentions Atlantis.", None)])
        answer, refs = react_loop.react_loop("Q?", self.path, client=client, with_refs=True)
        self.assertEqual((answer, refs), ("I don't know - nothing mentions Atlantis.", []))
        errors = [m["content"] for m in client.requests[-1]["messages"] if m["role"] == "tool"]
        self.assertTrue(errors[0].startswith("Tool error in search: JSONDecodeError"))
        self.assertIn("Try search, or find_mentions", errors[1])
        self.assertIn("No article mentions 'atlantis'", errors[2])

    def test_last_step_forbids_tools(self):
        loop = [(None, [tool_call(i, "search", {"query": "frog"})]) for i in range(3)]
        client = FakeClient(loop)
        self.assertEqual(react_loop.react_loop("Q?", self.path, client=client, max_steps=3), "I don't know")
        self.assertEqual([r["tool_choice"] for r in client.requests], ["auto", "auto", "none"])
        self.assertEqual(react_loop.run_tool({}, "bogus", {}), "Unknown tool 'bogus'.")

    def test_references_are_validated_against_shown_rows(self):
        read = (None, [tool_call(1, "read_article", {"title": "Luminous Tree Frog"})])
        _, start = react_loop.index.get_index(self.path)["docs"]["Luminous Tree Frog"]
        frog_tag = f"[-1:{start + 1}]"  # fixture pages have no <id>; the fact is on the text's 2nd line
        for final, expected_lines in [(f"fewer than 3,000\nSOURCES: {frog_tag} [42:7]", [start + 1]),
                                      ("3,000", [start + 1]),  # no citation: rows containing the answer
                                      ("I don't know\nSOURCES: " + frog_tag, [])]:
            client = FakeClient([read, (final, None)])
            answer, refs = react_loop.react_loop("Q?", self.path, client=client, with_refs=True)
            self.assertNotIn("SOURCES", answer)
            self.assertEqual([r["xml_line"] for r in refs], expected_lines, final)
        self.assertIn(frog_tag + " Current population", client.requests[-1]["messages"][-1]["content"])
        self.assertEqual(refs, [])

    def test_prompt_requires_backlink_search_before_giving_up(self):
        # Hard example: the expedition's infobox names "Starrise"; only the valley article says
        # the expedition launched there, so a dead end must trigger find_mentions on the entity.
        self.assertIn("call find_mentions\nwith the exact name of each entity", react_loop.SYSTEM)
        self.assertIn("override the entity's own infobox", react_loop.SYSTEM)


if __name__ == "__main__":
    unittest.main()
