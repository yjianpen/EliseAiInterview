# Practical Interview

## Overview

Implement `answer()` so it can answer questions from a large XML file of fictional Wikipedia-style articles. Return `"I don't know"` when the information is not available.

You are given:

1. A large XML file (`data/enwiki/enwiki-1gb.xml`) of fictional articles
2. A template (`src/candidate_solution.py`) with an `answer()` function and two inline example questions for local testing

## Setup

### Prerequisites

- Python 3.10 or higher
- pip
- An OpenAI API key (required to run the evaluator)

### Installation

Run these from the `candidate/` directory.

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Download the Wikipedia data file:

```bash
python setup.py
```

This downloads and extracts the ~1GB XML file into `data/enwiki/`.

3. Set your OpenAI API key:
```bash
export OPENAI_API_KEY="sk-your-key-here"
```
Or create a `.env` file in the `src/` directory:
```
OPENAI_API_KEY="sk-your-key-here"
```

### Check setup

```bash
cd src && python -c "import evaluator, crypto_utils; print('Setup OK')"
```

If you see import errors, confirm dependencies are installed and the API key is set.

## Project structure

```
candidate/
├── data/
│   ├── enwiki/
│   │   └── enwiki-1gb.xml       # Fictional Wikipedia articles (downloaded by setup)
│   └── encrypted_qa.json        # Encrypted evaluation set (interviewer use)
├── src/
│   ├── candidate_solution.py    # Implement `answer()` here (includes 2 example questions)
│   ├── evaluator.py             # Local evaluation helper
│   ├── crypto_utils.py
│   └── decrypt_and_evaluate.py  # Full evaluation (interviewer use)
├── setup.py
├── requirements.txt
└── README.md
```

## Your task

Implement `answer()` in `src/candidate_solution.py`:

```python
def answer(question: str, file_path: str) -> str:
    """
    Answer questions based on information in the Wikipedia articles file.

    Returns the answer as a string, or "I don't know" if unanswerable.
    """
```

Two example questions are inlined in that file as `EXAMPLES` so you can test locally. They are illustrative only and do not appear in the graded set.

```bash
cd src && python candidate_solution.py
```

When you are done, an interviewer will run the full evaluation against a separate encrypted question set.

## Current solution

`answer()` in `src/candidate_solution.py`:
1. **ReAct agent** (`react_loop`) — parses the question into hops and calls `search` / `read_article` /
   `find_mentions` until it can answer, or says `I don't know`.
2. **Fallback on errors only** (`fallback_answer`) — BM25 top 8 + 2 wiki-link hops (`retrieve`), then one LLM
   call over those articles. A refusal from step 1 is final, so the fallback cannot invent an answer for it.
3. If both fail, return `I don't know`; `answer()` never raises.

Setup: `pip install -r requirements.txt`, then put `OPENAI_API_KEY="..."` in `src/.env` (gitignored).

```bash
python3 -m unittest tests.test_candidate_solution -v   # project root, no key needed -> OK
cd src && python3 candidate_solution.py                # needs the key -> both examples graded correct
```

## Solution progress

### Indexer (`src/index.py`)

- `get_index(file_path)` parses the XML dump once per process (thread-safe) and caches it as
  `<dump>.idx.pkl` next to the dump: ~20s to build cold, ~1s to reload from the pickle.
- The index holds cleaned article text (refs/markup stripped, links flattened, infobox fields kept),
  the outgoing links of each article, and a case-insensitive alias map that resolves redirects.
- Tests: `cd src && python3 -m unittest test_index -v`

### Retrieval tools (`src/search.py`)

The tools the agent will call, all taking the index from `get_index()`:

- `search(index, query, k)` — BM25 over title + first 12K chars of each article (title terms boosted).
  The term index is built lazily once per process: ~8s, ~1.4GB peak with the index loaded.
- `read_article(index, title)` — resolves loose titles (case, redirects, partial like
  "Lunar Cartography Expedition", typos) and returns the full text plus its outgoing links for link hops.
- `find_mentions(index, phrase)` — backlink search over full text (~3s). Needed when the fact that
  links two articles lives only in the *other* article (e.g. the valley says the expedition launched there).
- Tests: `cd src && python3 -m unittest test_search -v`

### ReAct loop (`src/react_loop.py`)

- `react_loop(question, file_path, client=None)` — the model first parses the question into entities
  and a chain of hops, then alternates thought → tool call (`search` / `read_article` / `find_mentions`)
  → observation, up to 8 steps. The last step disables tools to force an answer.
- `normalize_answer()` maps any refusal ("Unknown", "not stated", ...) to exactly `I don't know`.
- Model: `gpt-4.1-mini`, override with `OPENAI_MODEL`. Key: `OPENAI_API_KEY` in the environment or `src/.env`.
- Tests use a scripted fake client (no key or network): `cd src && python3 -m unittest test_react_loop -v`

### TODO


- Make final answers terser (live runs reply with full sentences)
- Speed up `find_mentions` (precomputed lowercase text or a phrase index); pickle the BM25 index
- Custom eval set (multi-hop, conflicting sources, "current" values, unanswerable)
- Optional: all-fictional-articles-in-context mode, section-level chunking, tool-call trace logging
