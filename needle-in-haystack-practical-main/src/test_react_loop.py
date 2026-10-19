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

    def test_refusals_are_normalized(self):
        for reply in ["I don't know.", "Unknown", "  not stated in the articles", "", None]:
            client = FakeClient([(reply, None)])
            self.assertEqual(react_loop.react_loop("Q?", self.path, client=client), "I don't know")
        self.assertEqual(react_loop.normalize_answer(' "Skyfather\'s Breath" '), "Skyfather's Breath")

    def test_last_step_forbids_tools(self):
        loop = [(None, [tool_call(i, "search", {"query": "frog"})]) for i in range(3)]
        client = FakeClient(loop)
        self.assertEqual(react_loop.react_loop("Q?", self.path, client=client, max_steps=3), "I don't know")
        self.assertEqual([r["tool_choice"] for r in client.requests], ["auto", "auto", "none"])
        self.assertEqual(react_loop.run_tool({}, "bogus", {}), "Unknown tool 'bogus'.")

    def test_prompt_requires_backlink_search_before_giving_up(self):
        # Hard example: the expedition's infobox names "Starrise"; only the valley article says
        # the expedition launched there, so a dead end must trigger find_mentions on the entity.
        self.assertIn("call find_mentions\nwith the exact name of each entity", react_loop.SYSTEM)
        self.assertIn("override the entity's own infobox", react_loop.SYSTEM)


if __name__ == "__main__":
    unittest.main()
