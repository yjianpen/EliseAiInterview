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
4. `answer()` prints the agent's references as one block per question, e.g.
   `[7183942:4685499] Aethermist Valley | The indigenous Norathi people ...` (page id : XML line). The returned
   string stays answer-only so grading is unaffected; the error fallback path has no references.

Setup: `pip install -r requirements.txt`, then put `OPENAI_API_KEY="..."` in `src/.env` (gitignored).

```bash
python3 -m unittest tests.test_candidate_solution -v   # project root, no key needed -> OK
cd src && python3 candidate_solution.py                # needs the key -> both examples graded correct
```

## Solution progress

### Indexer (`src/index.py`)

- `get_index(file_path)` parses the XML dump once per process (thread-safe) and caches it as
  `<dump>.v2.idx.pkl` next to the dump: ~20s to build cold, ~1s to reload from the pickle.
- The index holds cleaned article text (refs/markup stripped, links flattened, infobox fields kept),
  the outgoing links of each article, and a case-insensitive alias map that resolves redirects.
- `index["docs"][title] = (page_id, xml_line)`: row *i* of an article's cleaned text comes from line
  `xml_line + i` of the XML file (cleaning keeps line positions). Verified on 45,906 rows of the real dump.
  Page ids are not unique in this dump (3847291 is used twice), so references use page id + XML line.
- Cache file is `<dump>.v2.idx.pkl`; the old `<dump>.idx.pkl` from before line tracking can be deleted.
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
- Prompt rule: on a dead end or before `I don't know`, backlink-search every entity named in the question
  (fixes the hard example, where the expedition's infobox points to the wrong launch site).
- References: every observation row is tagged `[page_id:xml_line]` (from `index["docs"]`); the model ends with
  `SOURCES: [..]`. Only tags the tools actually showed are kept (else: shown rows containing the answer), so
  references are deterministic. `react_loop(q, f, with_refs=True)` returns `(answer, refs)`; `answer()` is unchanged.
- Retrieval failures go back to the agent as observations instead of ending the loop: tool exceptions and
  malformed arguments (`Tool error in search: ...`), and empty results that say what to try next.
- `read_article` observations append "Linked from" rows (inverted `[[link]]` graph, built once in ~0.4s) and mark
  links with no article; the prompt says to check every candidate of a hop. Hard example: 6/10 -> 10/10.
- Refusals are the agent's own words: the prompt asks it to start with "I don't know" plus at most one sentence
  on what is missing, never a related fact. `normalize_answer()` only trims (and strips one pair of wrapping
  quotes); an empty reply becomes `I don't know`. Refusals carry no references.
- Model: `gpt-4.1-mini`, override with `OPENAI_MODEL`. Key: `OPENAI_API_KEY` in the environment or `src/.env`.
- Tests use a scripted fake client (no key or network): `cd src && python3 -m unittest test_react_loop -v`

### Custom eval (`src/custom_eval.json`, `src/run_eval.py`)

21 questions written from the 28 fictional articles, every answer checked against the article text:
lookup (2), current_value (3), backlink (3: the fact lives only in *another* article), multi_hop (5),
conflicting (3: prose vs infobox years), unanswerable (5: expected `I don't know`).

```bash
cd src && python3 run_eval.py                          # all 21; needs the key, ~70s
cd src && python3 run_eval.py --category multi_hop     # one category
cd src && python3 -m unittest test_run_eval -v         # offline tests of the runner
```

Results (`gpt-4.1-mini` agent, 2 runs): **85.7% and 90.5%**. backlink, conflicting and current_value 3/3 in both.
Misses: "Who founded the Festival of Floating Lanterns?" both runs (the agent backlink-searches first, reads the
*library's* article and answers its founder); one multi-hop question per run (a different one each time);
once, a description of the expedition's balloon given as its unstated name.
After graceful refusals + tool failures fed back to the agent: full eval **21/21 (100%)** in 1 run; unanswerable
5/5 and 4/5 in 2 extra runs (the balloon question still sometimes gets a description instead of a refusal).

### Edge-case evals (`src/answers_not_exist_eval.py`, `src/synonyms.py`)

Each file defines `QA` (same item format as `custom_eval.json`) and runs itself through `run_eval.py`, which now
also accepts `--qa <file>.py`:

- `answers_not_exist_eval.py` — 26 questions whose answer is not in the dump (expected `I don't know`):
  invented entities (9, names absent from all 20,399 articles), missing attributes of real fictional entities
  (15), a false premise and a future value. Result: **26/26**.
- `synonyms.py` — 25 questions naming entities by alias (`also_known_as`), abbreviation (CTTA, IIA, ...),
  scientific name (*Hyla bioluminescens*) or paraphrase (founded → started, population → how many people live).
  Result: **25/25**.

```bash
cd src && python3 answers_not_exist_eval.py          # or: python3 synonyms.py --category abbreviation
```

### TODO

- Prompt: read the entity's own article before `find_mentions` (fixes the festival-founder miss)
- Multi-hop flakiness: try `OPENAI_MODEL=gpt-4.1`, or run twice and re-ask on disagreement
- Make final answers terser (live runs reply with full sentences)
- Speed up `find_mentions` (precomputed lowercase text or a phrase index); pickle the BM25 index
- Optional: all-fictional-articles-in-context mode, section-level chunking, tool-call trace logging
