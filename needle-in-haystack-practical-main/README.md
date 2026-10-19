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
