"""ReAct loop: the model parses the question into hops, calls retrieval tools, then answers."""
import json
import os
import re

import index
import search

DONT_KNOW = "I don't know"
_TAG = re.compile(r"\[(-?\d+):(\d+)\]")
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
Each observation row starts with a [page_id:xml_line] tag.
Final reply: only the short answer (a name, number or phrase), then a new line "SOURCES:" followed by the
tags of the rows that state it. If it is not stated, reply: I don't know"""
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


def run_tool(idx: dict, name: str, args: dict, seen: dict = None) -> str:
    """Execute one tool call; every row of the observation carries a deterministic [page_id:xml_line] tag."""
    seen = {} if seen is None else seen
    if name == "search":
        hits = search.search(idx, args.get("query", ""))
        return "\n\n".join(f"## {t}\n" + tag_rows(idx, t, 0, s, seen) for t, s in hits) or "No results."
    if name == "read_article":
        out = search.read_article(idx, args.get("title", ""))
        title = out[2:out.find("\n")] if out.startswith("# ") else None
        if title not in idx["pages"]:
            return out
        body, links = out[len(title) + 3:].rsplit("\n\nLinks to: ", 1)
        return f"# {title}\n{tag_rows(idx, title, 0, body, seen)}\n\nLinks to: {links}"
    if name == "find_mentions":
        phrase, parts = args.get("phrase", "").strip().lower(), []
        for t, _ in search.find_mentions(idx, phrase):
            text = idx["pages"][t]
            row = text.count("\n", 0, text.lower().find(phrase))
            context = "\n".join(text.split("\n")[max(row - 1, 0):row + 2])
            parts.append(f"## {t}\n" + tag_rows(idx, t, max(row - 1, 0), context, seen))
        return "\n\n".join(parts) or "No articles mention it."
    return f"Unknown tool '{name}'."


def normalize_answer(text: str) -> str:
    """Trim the final reply; map every refusal phrasing to exactly DONT_KNOW."""
    text = (text or "").strip().strip('"').strip()
    refusals = ("i don't know", "i do not know", "unknown", "not stated", "not mentioned",
                "no information", "cannot be determined", "the answer is not")
    return DONT_KNOW if not text or text.lower().startswith(refusals) else text


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
            if not cited and answer != DONT_KNOW:  # fall back to shown rows containing the answer
                cited = [tag for tag, (_, row) in seen.items() if answer.lower() in row.lower()]
            refs = [] if answer == DONT_KNOW else [
                {"page_id": p, "xml_line": l, "title": seen[(p, l)][0], "text": seen[(p, l)][1]}
                for p, l in sorted(set(cited))]
            break
        messages.append({"role": "assistant", "content": msg.content, "tool_calls": [
            {"id": c.id, "type": "function",
             "function": {"name": c.function.name, "arguments": c.function.arguments}}
            for c in msg.tool_calls]})
        for call in msg.tool_calls:
            args = json.loads(call.function.arguments or "{}")
            observation = run_tool(idx, call.function.name, args, seen)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": observation})
    return (answer, refs) if with_refs else answer
