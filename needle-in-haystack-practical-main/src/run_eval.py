#!/usr/bin/env python3
"""Run answer() on the custom eval set; print accuracy per difficulty (Evaluator) and per category."""
import argparse
import json
import os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(HERE, "..", "data", "enwiki", "enwiki-1gb.xml")


def main(argv=None, answer_fn=None, evaluator_cls=None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qa", default=os.path.join(HERE, "custom_eval.json"), help="JSON list of Q&A items")
    parser.add_argument("--category", help="run one category only, e.g. multi_hop or unanswerable")
    parser.add_argument("--workers", type=int, default=5)
    args = parser.parse_args(argv)
    with open(args.qa) as f:
        qa = [item for item in json.load(f) if args.category in (None, item["category"])]
    if answer_fn is None:
        from candidate_solution import answer as answer_fn
    if evaluator_cls is None:
        from evaluator import Evaluator as evaluator_cls
    summary = evaluator_cls(qa, verbose=True).run_evaluation(answer_fn, DATA_FILE, max_workers=args.workers)
    category = {item["question"]: item["category"] for item in qa}
    totals, correct = Counter(), Counter()
    for result in summary["detailed_results"]:
        totals[category[result["question"]]] += 1
        correct[category[result["question"]]] += bool(result.get("is_correct"))
    summary["by_category"] = {c: (correct[c], totals[c]) for c in sorted(totals)}
    print("Results by category:")
    for c, (ok, n) in summary["by_category"].items():
        print(f"  {c:14s}: {ok:2d}/{n:2d}")
    return summary


if __name__ == "__main__":
    main()
