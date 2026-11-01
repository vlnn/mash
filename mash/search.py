from typing import NamedTuple

from mash import axes, match
from mash.tree import Stored


class Hit(NamedTuple):
    score: int
    stored: Stored
    time: float


def search(stored_records, query, touched=None):
    touched = touched or {}
    browsing = not query.words and not query.tags
    hits = []
    for stored in stored_records:
        if not axes.in_subtree(query.node, stored):
            continue
        points = match.score(query, stored.record)
        if points or browsing:
            hits.append(Hit(points, stored, time_of(stored, touched)))
    return axes.order(hits, query.axes)


def time_of(stored, touched):
    return touched.get(stored.identity, stored.mtime)
