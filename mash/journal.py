import os
import time

COMPACT_AT = 10_000
ROOT = "."


def now():
    return time.time()


class Journal:
    def __init__(self, path):
        self.path = path

    def touch(self, node, head, action):
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(format_line(now(), node, head, action))
        if self.probably_long() and self.line_count() > COMPACT_AT:
            self.compact()

    def touched(self):
        latest = {}
        for stamp, node, head, _ in self.lines():
            latest[(node, head)] = max(stamp, latest.get((node, head), 0.0))
        return latest

    def forget(self, node, head):
        self.rewrite(lambda line: (line[1], line[2]) != (node, head))

    def forget_node(self, node):
        self.rewrite(lambda line: line[1] != node and not line[1].startswith(node + "/"))

    def compact(self):
        latest, counts = {}, {}
        for stamp, node, head, _ in self.lines():
            latest[(node, head)] = max(stamp, latest.get((node, head), 0.0))
            counts[(node, head)] = counts.get((node, head), 0) + 1
        self.write(
            format_line(latest[key], key[0], key[1], f"touched x{counts[key]}") for key in latest
        )

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


def format_line(stamp, node, head, action):
    return f"{int(stamp)}\t{node or ROOT}\t{head}\t{action}\n"


def parse_line(raw):
    parts = raw.rstrip("\n").split("\t")
    if len(parts) != 4:
        return None
    try:
        stamp = float(parts[0])
    except ValueError:
        return None
    node = "" if parts[1] == ROOT else parts[1]
    return stamp, node, parts[2], parts[3]
