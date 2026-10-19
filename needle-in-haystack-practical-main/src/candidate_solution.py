#!/usr/bin/env python3
"""
Practical Interview - Candidate Solution Template

Your task is to implement the 'answer' function below.
This function should search through the provided Wikipedia articles file
to find answers to various questions.
"""

def answer(question: str, file_path: str) -> str:
    """
    Answer questions based on information in the Wikipedia articles file.

    Args:
        question: The question to answer
        file_path: Path to the file containing Wikipedia articles

    Returns:
        The answer to the question, or "I don't know" if unanswerable
    """
    # TODO: Implement your solution here

    return "I don't know"


# Example questions to help you develop and test your solution.
# The graded evaluation uses a separate encrypted set of questions -- these
# two examples are illustrative only and will NOT appear in that set.
EXAMPLES = [
    {
        "question": "What do the Norathi people call the Aethermist Valley?",
        "answer": "Skyfather's Breath",
        "difficulty": "easy",
    },
    {
        "question": (
            "What is the current population estimate of the species that is "
            "endemic to the valley from which the Lunar Cartography Expedition "
            "was launched?"
        ),
        "answer": "3000",
        "difficulty": "hard",
    },
]


if __name__ == "__main__":
    import os
    import sys

    from evaluator import Evaluator

    data_file = os.path.join(
        os.path.dirname(__file__), "..", "data", "enwiki", "enwiki-1gb.xml"
    )

    if not os.path.exists(data_file):
        print(f"Error: Wikipedia XML file not found at {data_file}")
        print("Run `python setup.py` from the candidate/ directory first.")
        sys.exit(1)

    evaluator = Evaluator(EXAMPLES, verbose=True)
    evaluator.run_evaluation(answer, data_file, max_workers=5)
