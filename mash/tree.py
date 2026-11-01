import os
import pickle
from typing import NamedTuple

from mash import records

EXTENSION = ".txt"
ID_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
ID_LENGTH = 6
INDEX = ".index"
INDEX_VERSION = "mash-index-1"


class Stored(NamedTuple):
    record: records.Record
    node: str
    path: str
    mtime: float

    @property
    def name(self):
        return os.path.basename(self.path)[: -len(EXTENSION)]

    @property
    def identity(self):
        return identity_of(self.node, self.name)


class Tree:
    def __init__(self, root):
        self.root = root

    def load(self):
        index = self.read_index()
        fresh, changed = {}, False
        for node, entry in self.record_entries():
            mtime = entry.stat().st_mtime
            cached = index.get(entry.path)
            if cached and cached[0] == mtime:
                fresh[entry.path] = cached
            else:
                fresh[entry.path] = (mtime, node, read_record(entry.path))
                changed = True
        if changed or len(fresh) != len(index):
            self.write_index(fresh)
        return [Stored(record, node, path, mtime) for path, (mtime, node, record) in fresh.items()]

    def read_index(self):
        try:
            with open(os.path.join(self.root, INDEX), "rb") as f:
                version, index = pickle.load(f)
        except (OSError, pickle.UnpicklingError, EOFError, ValueError, TypeError):
            return {}
        return index if version == INDEX_VERSION else {}

    def write_index(self, index):
        if os.path.isdir(self.root):
            write_bytes_atomically(
                os.path.join(self.root, INDEX), pickle.dumps((INDEX_VERSION, index))
            )

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

    def children(self, node):
        folder = os.path.join(self.root, *node.split("/")) if node else self.root
        if not os.path.isdir(folder):
            return []
        with os.scandir(folder) as entries:
            names = sorted(e.name for e in entries if e.is_dir() and not e.name.startswith("."))
        return [join_node(node, name) for name in names]

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
        path = os.path.join(folder, f"{records.slug(record.head)}.{new_id()}{EXTENSION}")
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


def node_counts(stored_records):
    counts = {}
    for stored in stored_records:
        node = stored.node
        while node:
            counts[node] = counts.get(node, 0) + 1
            node = node.rpartition("/")[0]
    return counts


def read_record(path):
    with open(path, encoding="utf-8", errors="surrogateescape") as f:
        return records.parse(f.read())


def join_node(node, name):
    return f"{node}/{name}" if node else name


def new_id():
    return "".join(ID_ALPHABET[b % len(ID_ALPHABET)] for b in os.urandom(ID_LENGTH))


def identity_of(node, name):
    slug, dot, suffix = name.rpartition(".")
    if dot and len(suffix) == ID_LENGTH and all(c in ID_ALPHABET for c in suffix):
        return suffix
    return join_node(node, name)


def write_atomically(path, text):
    write_bytes_atomically(path, text.encode("utf-8", errors="surrogateescape"))


def write_bytes_atomically(path, data):
    temporary = path + ".tmp"
    with open(temporary, "wb") as f:
        f.write(data)
    os.replace(temporary, path)
