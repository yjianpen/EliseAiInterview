"""ReAct loop: the model parses the question into hops, calls retrieval tools, then answers."""
import json
import os
import re
import threading

import index
import search

DONT_KNOW = "I don't know"
_TAG = re.compile(r"\[(-?\d+):(\d+)\]")
_LOCK = threading.Lock()
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
SYSTEM = """Answer questions using ONLY a Wikipedia dump that also contains fictional articles.
First parse the question: name the entities it mentions and the chain of hops needed
(e.g. expedition -> valley it launched from -> species endemic there -> its population).
Then resolve one hop at a time with the tools. Use find_mentions when the link between two
entities may only be stated in the *other* article, and to check whether sources disagree.
Rely only on text you read through tools. If sources conflict, trust the one that states the exact
relationship the question describes. For "current"/"latest" values, use the most recent figure.
Before answering "I don't know", or when a hop dead-ends (no article for an entity), call find_mentions
with the exact name of each entity in the question (e.g. "Lunar Cartography Expedition"): other
articles often state the relationship you need, and they override the entity's own infobox.
When a hop matches several candidates (e.g. a valley with several endemic species), do not commit to the
first one: check each candidate and continue with the one whose article states the fact asked for. Links
marked "(no article)" have no article of their own. Answer "I don't know" only after every candidate fails.
Each observation row starts with a [page_id:xml_line] tag.
Final reply: only the short answer (a name, number or phrase), then a new line "SOURCES:" followed by the
tags of the rows that state it. Tool failures come back as observations: retry with another query or tool.
If the specific fact asked for is not stated in what you read, start your reply with "I don't know" and
add at most one short sentence on what is missing. Never offer a related fact, description or guess instead."""
TOOLS = [{"type": "function", "function": {"name": name, "description": desc, "parameters": {
    "type": "object", "properties": {arg: {"type": "string"}}, "required": [arg]}}}
    for name, arg, desc in [
        ("search", "query", "BM25 keyword search over article titles and leads."),
        ("read_article", "title", "Read an article by approximate title; ends with its outgoing links."),
        ("find_mentions", "phrase", "List other articles whose text mentions a phrase, with context."),
    ]]


def tag_rows(idx: dict, title: str, first_row: int, text: str, seen: dict) -> str:
    """Prefix each non-empty row with its [page_id:xml_line] tag and remember what was shown."""
    page_id, start = idx["docs"][title]
    out = []
    for offset, row in enumerate(text.split("\n")):
        if row.strip():
            tag = (page_id, start + first_row + offset)
            seen[tag] = (title, row.strip())
            out.append(f"[{tag[0]}:{tag[1]}] {row.strip()}")
    return "\n".join(out)


def backlinks(idx: dict, title: str) -> list:
    """Articles whose [[wiki links]] point at title; the link graph is inverted once per process (~0.4s)."""
    with _LOCK:
        if "backlinks" not in idx:
            inverted = {}
            for src, targets in idx["links"].items():
                for target in targets:
                    if idx["aliases"].get(target.lower()):
                        inverted.setdefault(idx["aliases"][target.lower()], []).append(src)
            idx["backlinks"] = inverted
    return idx["backlinks"].get(title, [])


def run_tool(idx: dict, name: str, args: dict, seen: dict = None) -> str:
    """Execute one tool call; every row of the observation carries a deterministic [page_id:xml_line] tag."""
    seen = {} if seen is None else seen
    if name == "search":
        hits = search.search(idx, args.get("query", ""))
        return "\n\n".join(f"## {t}\n" + tag_rows(idx, t, 0, s, seen) for t, s in hits) or (
            f"No results for '{args.get('query', '')}'. Try fewer or different keywords, or find_mentions.")
    if name == "read_article":
        out = search.read_article(idx, args.get("title", ""))
        title = out[2:out.find("\n")] if out.startswith("# ") else None
        if title not in idx["pages"]:
            return out + " Try search, or find_mentions with a shorter form of the name."
        body, links = out[len(title) + 3:].rsplit("\n\nLinks to: ", 1)
        links = ", ".join(l if l.lower() in idx["aliases"] else f"{l} (no article)" for l in links.split(", "))
        linked_from, key = [], " ".join(title.lower().split()[:3])  # the row in each source that names title
        for src in backlinks(idx, title)[:5]:
            rows = idx["pages"][src].split("\n")
            row = next((i for i, r in enumerate(rows) if key in r.lower()), None)
            if row is not None:
                linked_from.append(f"## {src}\n" + tag_rows(idx, src, row, rows[row], seen))
        backs = "\n\nLinked from (these articles may state facts about it):\n" + "\n".join(linked_from)
        return (f"# {title}\n{tag_rows(idx, title, 0, body, seen)}\n\nLinks to: {links}"
                + (backs if linked_from else ""))
    if name == "find_mentions":
        phrase, parts = args.get("phrase", "").strip().lower(), []
        for t, _ in search.find_mentions(idx, phrase):
            text = idx["pages"][t]
            row = text.count("\n", 0, text.lower().find(phrase))
            context = "\n".join(text.split("\n")[max(row - 1, 0):row + 2])
            parts.append(f"## {t}\n" + tag_rows(idx, t, max(row - 1, 0), context, seen))
        return "\n\n".join(parts) or (
            f"No article mentions '{phrase}'. If no other entity leads to the fact, it is not in the dump.")
    return f"Unknown tool '{name}'."


def normalize_answer(text: str) -> str:
    """Trim whitespace and one pair of wrapping quotes. Refusals keep the agent's own wording
    ("I don't know - ..."); only an empty reply becomes DONT_KNOW."""
    text = (text or "").strip()
    if len(text) > 1 and text[0] == text[-1] == '"':
        text = text[1:-1].strip()
    return text or DONT_KNOW


def react_loop(question: str, file_path: str, client=None, max_steps: int = 8, with_refs: bool = False):
    """Think/act/observe until the model answers; the last step forbids tools to force an answer.
    with_refs=True returns (answer, refs): refs are rows the tools actually showed, as dicts with page_id,
    xml_line, title, text; cited tags the model never saw are dropped."""
    if client is None:
        import openai
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
        client = openai.OpenAI()
    idx = index.get_index(file_path)
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
    seen, answer, refs = {}, DONT_KNOW, []
    for step in range(max_steps):
        msg = client.chat.completions.create(
            model=MODEL, temperature=0, messages=messages, tools=TOOLS,
            tool_choice="none" if step == max_steps - 1 else "auto").choices[0].message
        if not msg.tool_calls:
            reply, _, sources = (msg.content or "").partition("SOURCES:")
            answer = normalize_answer(_TAG.sub("", reply))
            cited = [(int(p), int(l)) for p, l in _TAG.findall(sources + reply) if (int(p), int(l)) in seen]
            refused = answer.lower().startswith(("i don't know", "i do not know"))
            if not cited and not refused:  # fall back to shown rows containing the answer
                cited = [tag for tag, (_, row) in seen.items() if answer.lower() in row.lower()]
            refs = [] if refused else [
                {"page_id": p, "xml_line": l, "title": seen[(p, l)][0], "text": seen[(p, l)][1]}
                for p, l in sorted(set(cited))]
            break
        messages.append({"role": "assistant", "content": msg.content, "tool_calls": [
            {"id": c.id, "type": "function",
             "function": {"name": c.function.name, "arguments": c.function.arguments}}
            for c in msg.tool_calls]})
        for call in msg.tool_calls:
            try:
                args = json.loads(call.function.arguments or "{}")
                observation = run_tool(idx, call.function.name, args, seen)
            except Exception as exc:  # retrieval failures go back to the agent instead of ending the loop
                observation = (f"Tool error in {call.function.name}: {exc!r}. Try another query or tool; "
                               "if the fact cannot be found, answer I don't know.")
            messages.append({"role": "tool", "tool_call_id": call.id, "content": observation})
    return (answer, refs) if with_refs else answer
