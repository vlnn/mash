import re
from functools import cache

WHOLE, START, INNER, FUZZY, BODY = 8, 6, 4, 2, 1
TIERS = (("whole", WHOLE), ("start", START), ("inner", INNER), ("fuzzy", FUZZY))


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
        points = max((score_tag(term, tag) for tag in record.tags), default=0)
        if not points:
            return 0
        total += points
    return total


def score_word(term, record):
    best = max((score_head_word(term, word) for word in record.words), default=0)
    return best or score_body(term, record.body)


def score_head_word(term, word):
    if word.startswith("#"):
        return score_tag("#" + term, word)
    match = head_pattern(term).match(word.lower())
    if not match:
        return 0
    return next(points for name, points in TIERS if match.group(name))


def score_tag(term, tag):
    term, tag = term.lower(), tag.lower()
    if term == tag:
        return WHOLE
    if tag.startswith(term):
        return START
    return 0


def score_body(term, body):
    pattern = fuzzy_pattern(term)
    return BODY if any(pattern.search(word) for word in body.lower().split()) else 0


@cache
def head_pattern(term):
    literal = re.escape(term.lower())
    letters = letters_in_order(term)
    return re.compile(
        f"^(?:(?P<whole>{literal})$|(?P<start>{literal})|(?P<inner>.*?{literal})|(?P<fuzzy>{letters}))"
    )


@cache
def fuzzy_pattern(term):
    return re.compile(letters_in_order(term))


def letters_in_order(term):
    return ".*?".join(re.escape(c) for c in term.lower())
