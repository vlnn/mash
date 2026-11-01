from typing import NamedTuple, Optional

from mash import records

NODE_END = "/"


class Query(NamedTuple):
    words: tuple
    tags: tuple
    node: str
    axes: str
    add: Optional[records.Record]


def parse(text):
    match = records.ARROW.search(text)
    before = text[: match.start()] if match else text
    node, head = take_node(before)
    if match and head.strip():
        return add_query(node, head + text[match.start() :])
    if match:
        return search_query(node, axes_of(match.group(1)), text[match.end() :])
    return search_query(node, "", head)


def add_query(node, text):
    record = records.from_box(text)
    words, tags = split_tags(record.words)
    return Query(words, tags, node, "", record)


def search_query(node, axes, text):
    words, tags = split_tags(records.head_words(text))
    return Query(words, tags, node, axes, None)


def take_node(text):
    terms = text.split()
    parts = [t.strip(NODE_END) for t in terms if is_node(t)]
    remaining = [t for t in terms if not is_node(t)]
    return "/".join(parts), " ".join(remaining)


def is_node(term):
    return term.endswith(NODE_END) and len(term) > 1


def axes_of(arrow):
    return arrow[:-1].replace("=", "")


def split_tags(words):
    tags = tuple(w for w in words if w.startswith("#"))
    plain = tuple(w for w in words if not w.startswith("#"))
    return plain, tags
