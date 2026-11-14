from typing import NamedTuple, Optional

from mash import axes, search
from mash import query as queries
from mash.tree import Stored

DEPTH_CAP = 8


class Resolution(NamedTuple):
    chain: list
    fact: Optional[Stored]
    error: str


def resolve(stored_records, start, touched=None):
    chain = [start]
    current = start
    while current.record.is_rule:
        if len(chain) >= DEPTH_CAP:
            return Resolution(chain, None, f"stopped at depth {DEPTH_CAP}")
        hit = best_hit(stored_records, current, touched)
        if hit is None:
            return Resolution(chain, None, f"nothing matches {current.record.query!r}")
        chain.append(hit)
        current = hit
    return Resolution(chain, current, "")


def best_hit(stored_records, rule, touched):
    query, pinned = rule_query(rule)
    candidates = [s for s in stored_records if s.path != rule.path and shares_tags(query, rule, s)]
    hits = search.search(candidates, query, touched)
    if not hits and not pinned:
        hits = search.search(candidates, query._replace(node=""), touched)
    return hits[0].stored if hits else None


def rule_query(rule):
    query = queries.parse(rule.record.query)
    combined = queries.axes_of(rule.record.arrow) + query.axes
    pinned = bool(query.node) or axes.SUBTREE in combined
    return query._replace(axes=combined, node=query.node or rule.node), pinned


def shares_tags(query, rule, stored):
    if axes.SAME_TAGS not in query.axes:
        return True
    return bool(set(rule.record.tags) & set(stored.record.tags))
