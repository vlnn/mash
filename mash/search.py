from typing import NamedTuple

from mash import axes, match
from mash.tree import Stored


class Hit(NamedTuple):
    score: int
    stored: Stored
    time: float


def search(stored_records, query, touched=None):
    touched = touched or {}
    candidates = (s for s in stored_records if axes.in_subtree(query.node, s))
    hits = (Hit(match.score(query, s.record), s, time_of(s, touched)) for s in candidates)
    if query.words or query.tags:
        hits = (hit for hit in hits if hit.score)
    return axes.order(hits, query.axes)


def time_of(stored, touched):
    return touched.get(identity(stored), stored.mtime)


def identity(stored):
    return stored.node, stored.record.head
