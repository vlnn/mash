import re
from typing import NamedTuple

FACT_ARROW = "->"
ARROW = re.compile(r"(?:^|\s)(->|[=~/#]+>)(?=\s|$)")
WORD_SPLIT = re.compile(r"[\s,]+")
PUNCTUATION = re.compile(r"[^\w-]+")
BOX_NEWLINE = re.compile(r"(?<!\\);;")
ESCAPED_BOX_NEWLINE = "\\;;"


class Record(NamedTuple):
    head: str
    words: tuple
    tags: tuple
    arrow: str
    body: str
    query: str
    searchable: str
    body_words: str

    @property
    def is_rule(self):
        return self.arrow != FACT_ARROW


def parse(text):
    first, rest = split_first_line(text)
    match = ARROW.search(first)
    if not match:
        return fact(first.strip(), strip_final_newline(text))
    head = first[: match.start()].strip()
    arrow = match.group(1)
    after = first[match.end() :].strip()
    if arrow == FACT_ARROW:
        return fact(head, join_body(after, rest))
    return rule(head, arrow, after)


def fact(head, body):
    words = head_words(head)
    return Record(
        head, words, tags_of(words), FACT_ARROW, body, "", searchable(words), body_words(body)
    )


def rule(head, arrow, query):
    words = head_words(head)
    return Record(head, words, tags_of(words), arrow, "", query, searchable(words), "")


def from_box(line):
    return parse(BOX_NEWLINE.sub("\n", line).replace(ESCAPED_BOX_NEWLINE, ";;"))


def render(record):
    if record.is_rule:
        return f"{record.head} {record.arrow} {record.query}\n"
    if record.body == record.head:
        return record.head + "\n"
    return f"{record.head} {record.arrow} {record.body}\n"


def slug(head):
    dashed = "".join(c if c.isalnum() else "-" for c in head.lower())
    collapsed = re.sub(r"-+", "-", dashed).strip("-")
    return collapsed or "record"


def split_first_line(text):
    first, _, rest = text.partition("\n")
    return first, strip_final_newline(rest)


def strip_final_newline(text):
    return text[:-1] if text.endswith("\n") else text


def join_body(after, rest):
    if after and rest:
        return f"{after}\n{rest}"
    return after or rest


def head_words(head):
    return tuple(w for w in WORD_SPLIT.split(head) if w)


def tags_of(words):
    return tuple(w for w in words if w.startswith("#"))


def searchable(words):
    return " ".join(w for w in words if not w.startswith("#")).lower()


def body_words(body):
    return PUNCTUATION.sub(" ", body.lower())
