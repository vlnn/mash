import re
from functools import cache

WHOLE, START, INNER, FUZZY, BODY = 8, 6, 4, 2, 1


def score(query, record):
    if not query.words and not query.tags:
        return 0
    total = 0
    for term in query.words:
        points = score_word(term, record)
        if not points:
            return 0
        total += points
    for term in query.tags:
        points = score_tags(term, record.tags)
        if not points:
            return 0
        total += points
    return total


def score_word(term, record):
    return (
        score_head(term, record.searchable)
        or score_tags("#" + term, record.tags)
        or score_body(term, record.body_words)
    )


def score_tags(term, tags):
    best = 0
    for tag in tags:
        best = max(best, score_tag(term, tag))
    return best


def score_head(term, head):
    tiers = head_patterns(term)
    if not tiers[FUZZY].search(head):
        return 0
    for points in (WHOLE, START, INNER):
        if tiers[points].search(head):
            return points
    return FUZZY


def score_head_word(term, word):
    if word.startswith("#"):
        return score_tag("#" + term, word)
    return score_head(term, word.lower())


def score_tag(term, tag):
    term, tag = term.lower(), tag.lower()
    if term == tag:
        return WHOLE
    if tag.startswith(term):
        return START
    return 0


def score_body(term, body_words):
    return BODY if fuzzy_pattern(term).search(body_words) else 0


@cache
def head_patterns(term):
    literal = re.escape(term.lower())
    return {
        WHOLE: re.compile(rf"(?:^|\s){literal}(?=\s|$)"),
        START: re.compile(rf"(?:^|\s){literal}"),
        INNER: re.compile(literal),
        FUZZY: re.compile(rf"(?:^|\s)\S*?{letters_in_order(term)}"),
    }


@cache
def fuzzy_pattern(term):
    return re.compile(rf"(?:^|\s)\S*?{letters_in_order(term)}")


def letters_in_order(term):
    return r"\S*?".join(re.escape(c) for c in term.lower())
