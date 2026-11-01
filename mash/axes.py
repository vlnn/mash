OLDEST_FIRST = "~"
SUBTREE = "/"
SAME_TAGS = "#"


def in_subtree(node, stored):
    return not node or stored.node == node or stored.node.startswith(node + "/")


def order(hits, axes):
    direction = 1 if OLDEST_FIRST in axes else -1
    return sorted(hits, key=lambda hit: (-hit.score, tightness(hit), direction * hit.time))


def tightness(hit):
    return len(hit.stored.record.words) if hit.score else 0
