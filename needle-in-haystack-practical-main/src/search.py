"""Retrieval tools over the index from index.get_index(): the agent's search/read/backlink calls."""
import difflib
import math
import re
import threading
from collections import Counter, defaultdict

_TOK = re.compile(r"[a-z0-9]+")
_STOP = frozenset(
    "the a an of to in that is was were are be for with on by as at this which who what "
    "where when how do does did from and or its their they them it his her".split())
_LEAD_CHARS = 12000  # BM25 sees title + article lead; find_mentions/read_article see full text
_LOCK = threading.Lock()


def search(index: dict, query: str, k: int = 5) -> list:
    """BM25 over title + lead text (title terms boosted). Returns [(title, snippet)]."""
    with _LOCK:
        if "bm25" not in index:  # inverted index: term -> {title: tf}, built once per process
            postings, lengths = defaultdict(dict), {}
            for title, text in index["pages"].items():
                tf = Counter(t for t in _TOK.findall(f"{title} {text[:_LEAD_CHARS]}".lower())
                             if t not in _STOP)
                lengths[title] = sum(tf.values()) or 1
                for term, n in tf.items():
                    postings[term][title] = n
            index["bm25"] = (postings, lengths, sum(lengths.values()) / max(len(lengths), 1))
    postings, lengths, avgdl = index["bm25"]
    terms = [t for t in _TOK.findall(query.lower()) if t not in _STOP]
    scores, n_docs = Counter(), len(lengths)
    for term in set(terms):
        docs = postings.get(term, {})
        idf = math.log((n_docs - len(docs) + 0.5) / (len(docs) + 0.5) + 1.0)
        for title, tf in docs.items():
            tf += 3 if term in title.lower() else 0
            scores[title] += idf * tf * 2.5 / (tf + 1.5 * (0.25 + 0.75 * lengths[title] / avgdl))
    return [(t, index["pages"][t][:300]) for t, _ in scores.most_common(k)]


def read_article(index: dict, title: str, max_chars: int = 20000) -> str:
    """Resolve a loose title (case, redirect, partial, typo) and return its text plus outgoing links."""
    aliases, key = index["aliases"], title.strip().lower()
    found = aliases.get(key)
    if not found:
        partial = sorted((t for t in index["pages"] if key in t.lower()), key=len)
        close = difflib.get_close_matches(key, aliases.keys(), n=1, cutoff=0.8)
        found = partial[0] if partial else aliases[close[0]] if close else None
    if not found:
        return f"No article found for '{title}'."
    links = [l for l in index["links"].get(found, []) if ":" not in l][:60]
    return f"# {found}\n{index['pages'][found][:max_chars]}\n\nLinks to: {', '.join(links)}"


def find_mentions(index: dict, phrase: str, k: int = 10) -> list:
    """Backlinks: articles whose full text mentions phrase (case-insensitive). Returns [(title, context)]."""
    pattern, hits = re.compile(re.escape(phrase.strip()), re.I), []
    for title, text in index["pages"].items():
        m = pattern.search(text)
        if m and title.lower() != phrase.strip().lower():
            hits.append((title, text[max(m.start() - 200, 0):m.end() + 200]))
            if len(hits) >= k:
                break
    return hits
