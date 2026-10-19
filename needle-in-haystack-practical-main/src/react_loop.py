"""ReAct loop: the model parses the question into hops, calls retrieval tools, then answers."""
import json
import os

import index
import search

DONT_KNOW = "I don't know"
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
SYSTEM = """Answer questions using ONLY a Wikipedia dump that also contains fictional articles.
First parse the question: name the entities it mentions and the chain of hops needed
(e.g. expedition -> valley it launched from -> species endemic there -> its population).
Then resolve one hop at a time with the tools. Use find_mentions when the link between two
entities may only be stated in the *other* article, and to check whether sources disagree.
Rely only on text you read through tools. If sources conflict, trust the one that states the exact
relationship the question describes. For "current"/"latest" values, use the most recent figure.
Final reply: only the short answer (a name, number or phrase). If it is not stated, reply: I don't know"""
TOOLS = [{"type": "function", "function": {"name": name, "description": desc, "parameters": {
    "type": "object", "properties": {arg: {"type": "string"}}, "required": [arg]}}}
    for name, arg, desc in [
        ("search", "query", "BM25 keyword search over article titles and leads."),
        ("read_article", "title", "Read an article by approximate title; ends with its outgoing links."),
        ("find_mentions", "phrase", "List other articles whose text mentions a phrase, with context."),
    ]]


def run_tool(idx: dict, name: str, args: dict) -> str:
    """Execute one tool call and format its observation for the model."""
    if name == "search":
        hits = search.search(idx, args.get("query", ""))
        return "\n\n".join(f"## {t}\n{snippet}" for t, snippet in hits) or "No results."
    if name == "read_article":
        return search.read_article(idx, args.get("title", ""))
    if name == "find_mentions":
        hits = search.find_mentions(idx, args.get("phrase", ""))
        return "\n\n".join(f"## {t}\n...{ctx}..." for t, ctx in hits) or "No articles mention it."
    return f"Unknown tool '{name}'."


def normalize_answer(text: str) -> str:
    """Trim the final reply; map every refusal phrasing to exactly DONT_KNOW."""
    text = (text or "").strip().strip('"').strip()
    refusals = ("i don't know", "i do not know", "unknown", "not stated", "not mentioned",
                "no information", "cannot be determined", "the answer is not")
    return DONT_KNOW if not text or text.lower().startswith(refusals) else text


def react_loop(question: str, file_path: str, client=None, max_steps: int = 8) -> str:
    """Think/act/observe until the model answers; the last step forbids tools to force an answer."""
    if client is None:
        import openai
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
        client = openai.OpenAI()
    idx = index.get_index(file_path)
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
    for step in range(max_steps):
        msg = client.chat.completions.create(
            model=MODEL, temperature=0, messages=messages, tools=TOOLS,
            tool_choice="none" if step == max_steps - 1 else "auto").choices[0].message
        if not msg.tool_calls:
            return normalize_answer(msg.content)
        messages.append({"role": "assistant", "content": msg.content, "tool_calls": [
            {"id": c.id, "type": "function",
             "function": {"name": c.function.name, "arguments": c.function.arguments}}
            for c in msg.tool_calls]})
        for call in msg.tool_calls:
            observation = run_tool(idx, call.function.name, json.loads(call.function.arguments or "{}"))
            messages.append({"role": "tool", "tool_call_id": call.id, "content": observation})
    return DONT_KNOW
