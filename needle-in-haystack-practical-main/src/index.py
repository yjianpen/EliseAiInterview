"""Parse the enwiki XML dump into a cached, in-memory index of articles."""
import html
import os
import pickle
import re
import threading
import xml.etree.ElementTree as ET

_NS = "{http://www.mediawiki.org/xml/export-0.11/}"
_LINK = re.compile(r"\[\[([^\[\]|#]+)(?:#[^\[\]|]*)?(?:\|([^\[\]]*))?\]\]")
_CACHE = {}
_LOCK = threading.Lock()


def clean_wikitext(text: str) -> str:
    """Strip refs/comments/markup and flatten [[target|label]] links, keeping infobox fields."""
    text = html.unescape(html.unescape(text or ""))  # dump text is often double-escaped
    text = re.sub(r"<!--.*?-->|<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", text, flags=re.S)
    text = _LINK.sub(lambda m: m.group(2) or m.group(1), text)
    text = re.sub(r"'{2,}|<[^>]+>", "", text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def load_pages(file_path: str) -> dict:
    """Stream the dump into {"pages": title->clean text, "links": title->link targets,
    "aliases": lowercased title/redirect -> canonical title}."""
    pages, links, redirects = {}, {}, {}
    with open(file_path, "rb") as fh:
        for _, el in ET.iterparse(fh, events=("end",)):
            if el.tag != _NS + "page":
                continue
            title = el.findtext(_NS + "title")
            raw = el.findtext(f"{_NS}revision/{_NS}text") or ""
            redirect = el.find(_NS + "redirect")
            if redirect is not None:
                redirects[title] = redirect.get("title")
            else:
                links[title] = sorted({m.group(1).strip() for m in _LINK.finditer(raw)})
                pages[title] = clean_wikitext(raw)
            el.clear()
    aliases = {t.lower(): t for t in pages}
    for src, dst in redirects.items():
        if dst in pages:
            aliases.setdefault(src.lower(), dst)
    return {"pages": pages, "links": links, "aliases": aliases}


def get_index(file_path: str) -> dict:
    """Return the index for file_path, built once per process and pickled next to the dump."""
    with _LOCK:
        if file_path in _CACHE:
            return _CACHE[file_path]
        cache_path = file_path + ".idx.pkl"
        fresh = os.path.exists(cache_path) and os.path.getmtime(cache_path) >= os.path.getmtime(file_path)
        if fresh:
            with open(cache_path, "rb") as f:
                index = pickle.load(f)
        else:
            index = load_pages(file_path)
            try:
                with open(cache_path, "wb") as f:
                    pickle.dump(index, f, protocol=pickle.HIGHEST_PROTOCOL)
            except OSError:
                pass  # read-only data dir: keep the in-memory index only
        _CACHE[file_path] = index
        return index
