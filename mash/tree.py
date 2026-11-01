import os
from typing import NamedTuple

from mash import records

EXTENSION = ".txt"


class Stored(NamedTuple):
    record: records.Record
    node: str
    path: str
    mtime: float


class Tree:
    def __init__(self, root):
        self.root = root

    def load(self):
        return [
            Stored(read_record(entry.path), node, entry.path, entry.stat().st_mtime)
            for node, entry in self.record_entries()
        ]

    def read(self, path):
        return Stored(read_record(path), self.node_of(path), path, os.stat(path).st_mtime)

    def record_entries(self):
        if not os.path.isdir(self.root):
            return
        pending = [(self.root, "")]
        while pending:
            folder, node = pending.pop()
            with os.scandir(folder) as entries:
                for entry in sorted(entries, key=lambda e: e.name):
                    if entry.name.startswith("."):
                        continue
                    if entry.is_dir():
                        pending.append((entry.path, join_node(node, entry.name)))
                    elif entry.name.endswith(EXTENSION):
                        yield node, entry

    def nodes(self):
        counts = {}
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            node = self.node_of(os.path.join(dirpath, "x"))
            if node:
                counts[node] = sum(1 for n in filenames if n.endswith(EXTENSION))
        for node in sorted(counts, key=len, reverse=True):
            parent = os.path.dirname(node)
            if parent:
                counts[parent] += counts[node]
        return counts

    def add(self, node, record):
        folder = os.path.join(self.root, *node.split("/")) if node else self.root
        os.makedirs(folder, exist_ok=True)
        path = free_path(folder, records.slug(record.head))
        write_atomically(path, records.render(record))
        return path

    def delete(self, stored):
        current = self.read(stored.path)
        if current.record.head != stored.record.head:
            raise LookupError(f"{stored.path} no longer holds {stored.record.head!r}")
        os.remove(stored.path)

    def node_of(self, path):
        relative = os.path.relpath(os.path.dirname(path), self.root)
        return "" if relative == "." else relative.replace(os.sep, "/")


def read_record(path):
    with open(path, encoding="utf-8", errors="surrogateescape") as f:
        return records.parse(f.read())


def join_node(node, name):
    return f"{node}/{name}" if node else name


def free_path(folder, slug):
    candidate = os.path.join(folder, slug + EXTENSION)
    n = 2
    while os.path.exists(candidate):
        candidate = os.path.join(folder, f"{slug}-{n}{EXTENSION}")
        n += 1
    return candidate


def write_atomically(path, text):
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8", errors="surrogateescape") as f:
        f.write(text)
    os.replace(temporary, path)
