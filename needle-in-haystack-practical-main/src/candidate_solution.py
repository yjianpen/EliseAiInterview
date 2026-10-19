#!/usr/bin/env python3
"""Answer questions over the enwiki dump: ReAct agent first, BM25 + link-hop retrieval as fallback."""
import os
import sys

import index
import react_loop
import search

FALLBACK_PROMPT = ("Answer using ONLY the wiki articles. If unsupported, reply exactly: I don't know. "
                   "Return a short fact (name, number, or phrase). Prefer article prose over infoboxes "
                   "when they conflict.")


def retrieve(question: str, idx: dict, hops: int = 2, k: int = 8) -> list:
    """BM25 top-k, then follow wiki links `hops` times, preferring links that share question words."""
    words = set(search._TOK.findall(question.lower())) - search._STOP
    picked = [title for title, _ in search.search(idx, question, k=k)]
    for _ in range(hops):
        frontier = {link for title in picked for link in idx["links"].get(title, [])
                    if link in idx["pages"] and link not in picked}
        overlap = lambda link: len(words & set(search._TOK.findall(link.lower())))
        picked += sorted(frontier, key=lambda link: (-overlap(link), link))[:k]
    return [(title, idx["pages"][title]) for title in picked]


def fallback_answer(question: str, file_path: str, client=None) -> str:
    """Single LLM call over retrieved articles (the first, non-agentic solution)."""
    if client is None:
        import openai
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
        client = openai.OpenAI()
    docs = retrieve(question, index.get_index(file_path))[:12]
    context = "\n\n".join(f"Title: {title}\n{text[:12000]}" for title, text in docs)
    reply = client.chat.completions.create(model=react_loop.MODEL, temperature=0, messages=[
        {"role": "system", "content": FALLBACK_PROMPT},
        {"role": "user", "content": f"Articles:\n{context}\n\nQuestion: {question}"}])
    return react_loop.normalize_answer(reply.choices[0].message.content)


def format_references(question: str, refs: list) -> str:
    """One printable block per question: each cited row as [page_id:xml_line] title | text."""
    rows = [f"  [{r['page_id']}:{r['xml_line']}] {r['title']} | {r['text'][:160]}" for r in refs]
    return "\n".join([f"References for: {question}"] + (rows or ["  (none)"]))


def answer(question: str, file_path: str) -> str:
    """ReAct agent (prints its references); on any error fall back to retrieve + one LLM call; never raise.
    The returned string is only the answer, so grading is unaffected by the references."""
    try:
        result, refs = react_loop.react_loop(question, file_path, with_refs=True)
        print(format_references(question, refs), flush=True)  # one print per question: no interleaving
        return result
    except Exception as exc:  # API/network/tool errors must not crash the evaluator
        print(f"react_loop failed: {exc!r}", file=sys.stderr)
    try:
        return fallback_answer(question, file_path)
    except Exception as exc:
        print(f"fallback_answer failed: {exc!r}", file=sys.stderr)
    return react_loop.DONT_KNOW


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
