import json
import os
import unittest

import run_eval

CATEGORIES = {"lookup", "current_value", "backlink", "multi_hop", "conflicting", "unanswerable"}


class FakeEvaluator:
    """Stands in for evaluator.Evaluator (which needs an OpenAI key): exact-match grading."""
    def __init__(self, qa, verbose=True):
        self.qa = qa

    def run_evaluation(self, answer_fn, file_path, max_workers=None):
        return {"detailed_results": [
            {"question": q["question"], "is_correct": answer_fn(q["question"], file_path) == q["answer"]}
            for q in self.qa]}


class RunEvalTest(unittest.TestCase):
    def test_eval_set_is_well_formed(self):
        with open(os.path.join(run_eval.HERE, "custom_eval.json")) as f:
            qa = json.load(f)
        self.assertEqual({q["category"] for q in qa}, CATEGORIES)
        for q in qa:
            self.assertIn(q["difficulty"], {"easy", "medium", "hard"})
            self.assertEqual(q["category"] == "unanswerable", q["answer"] == "I don't know", q)

    def test_reports_accuracy_per_category(self):
        always_refuse = lambda question, file_path: "I don't know"
        summary = run_eval.main([], answer_fn=always_refuse, evaluator_cls=FakeEvaluator)
        self.assertEqual(summary["by_category"]["unanswerable"], (5, 5))
        self.assertEqual(summary["by_category"]["multi_hop"], (0, 5))

    def test_category_filter(self):
        summary = run_eval.main(["--category", "backlink"], answer_fn=lambda q, f: "x",
                                evaluator_cls=FakeEvaluator)
        self.assertEqual(summary["by_category"], {"backlink": (0, 3)})


if __name__ == "__main__":
    unittest.main()
