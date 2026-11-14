import os
import time

COMPACT_AT = 10_000
ROOT = "."


def now():
    return time.time()


class Journal:
    def __init__(self, path):
        self.path = path

    def touch(self, identity, action, node=""):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(format_line(now(), identity, node, action))
        if self.probably_long() and self.line_count() > COMPACT_AT:
            self.compact()

    def touched(self):
        latest = {}
        for stamp, identity, _, _ in self.lines():
            latest[identity] = max(stamp, latest.get(identity, 0.0))
        return latest

    def forget(self, identity):
        self.rewrite(lambda line: line[1] != identity)

    def forget_node(self, node):
        self.rewrite(lambda line: line[2] != node and not line[2].startswith(node + "/"))

    def compact(self):
        latest, nodes, counts = {}, {}, {}
        for stamp, identity, node, _ in self.lines():
            latest[identity] = max(stamp, latest.get(identity, 0.0))
            nodes[identity] = node
            counts[identity] = counts.get(identity, 0) + 1
        self.write(format_line(latest[i], i, nodes[i], f"touched x{counts[i]}") for i in latest)

    def rewrite(self, keep):
        self.write(format_line(*line) for line in self.lines() if keep(line))

    def write(self, lines):
        temporary = self.path + ".tmp"
        with open(temporary, "w", encoding="utf-8") as f:
            f.writelines(lines)
        os.replace(temporary, self.path)

    def lines(self):
        if not os.path.exists(self.path):
            return
        with open(self.path, encoding="utf-8", errors="replace") as f:
            for raw in f:
                parsed = parse_line(raw)
                if parsed:
                    yield parsed

    def probably_long(self):
        return os.path.getsize(self.path) > COMPACT_AT * len(format_line(0, "", "", ""))

    def line_count(self):
        with open(self.path, "rb") as f:
            return sum(1 for _ in f)


def format_line(stamp, identity, node, action):
    return f"{stamp:.3f}\t{identity}\t{node or ROOT}\t{action}\n"


def parse_line(raw):
    parts = raw.rstrip("\n").split("\t")
    if len(parts) != 4:
        return None
    try:
        stamp = float(parts[0])
    except ValueError:
        return None
    node = "" if parts[2] == ROOT else parts[2]
    return stamp, parts[1], node, parts[3]
