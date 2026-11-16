import os
import pickle
import shutil
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
    shipped: bool = False

    @property
    def name(self):
        return os.path.basename(self.path)[: -len(EXTENSION)]

    @property
    def identity(self):
        return identity_of(self.node, self.name)


class Snapshot(NamedTuple):
    records: list
    folders: dict

    def children(self, node):
        return sorted(folder for folder in self.folders if parent_of(folder) == node)

    def named_like(self, prefix):
        prefix = prefix.lower()
        return sorted(f for f in self.folders if f.rpartition("/")[2].lower().startswith(prefix))


class Tree:
    def __init__(self, root, mounts=None):
        self.root = root
        self.mounts = dict(mounts or {})

    def load(self):
        folders, files = self.walk()
        index = self.read_index()
        fresh, changed = {}, False
        for node, entry in files:
            mtime = entry.stat().st_mtime
            cached = index.get(entry.path)
            if cached and cached[0] == mtime:
                fresh[entry.path] = cached
            else:
                fresh[entry.path] = (mtime, node, read_record(entry.path))
                changed = True
        if changed or len(fresh) != len(index):
            self.write_index(fresh)
        records = stored_from(fresh, self.is_shipped)
        return Snapshot(records, subtree_counts(folders, records))

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
        return Stored(
            read_record(path),
            self.node_of(path),
            path,
            os.stat(path).st_mtime,
            self.is_shipped(path),
        )

    def walk(self):
        folders, files = walk_folder(self.root, "")
        for name, base in self.mounts.items():
            if os.path.isdir(base):
                mounted_folders, mounted_files = walk_folder(base, name)
                folders += [name, *mounted_folders]
                files += mounted_files
        return folders, files

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

    def own_folder(self, node):
        return os.path.join(self.root, *node.split("/"))

    def owns(self, node):
        return bool(node) and os.path.isdir(self.own_folder(node))

    def remove_node(self, node):
        shutil.rmtree(self.own_folder(node))

    def node_of(self, path):
        name, base = self.mount_of(path) or ("", self.root)
        relative = os.path.relpath(os.path.dirname(path), base)
        return name if relative == "." else join_node(name, relative.replace(os.sep, "/"))

    def mount_of(self, path):
        return next((mount for mount in self.mounts.items() if is_inside(mount[1], path)), None)

    def is_shipped(self, path):
        return self.mount_of(path) is not None


def walk_folder(root, root_node):
    folders, files = [], []
    pending = [(root, root_node)] if os.path.isdir(root) else []
    while pending:
        folder, node = pending.pop()
        with os.scandir(folder) as entries:
            for entry in sorted(entries, key=lambda e: e.name):
                if entry.name.startswith("."):
                    continue
                if entry.is_dir():
                    child = join_node(node, entry.name)
                    folders.append(child)
                    pending.append((entry.path, child))
                elif entry.name.endswith(EXTENSION):
                    files.append((node, entry))
    return folders, files


def is_inside(folder, path):
    return path.startswith(os.path.join(folder, ""))


def stored_from(index, is_shipped):
    return [
        Stored(record, node, path, mtime, is_shipped(path))
        for path, (mtime, node, record) in index.items()
    ]


def subtree_counts(folders, stored_records):
    counts = dict.fromkeys(folders, 0)
    for stored in stored_records:
        node = stored.node
        while node:
            counts[node] = counts.get(node, 0) + 1
            node = parent_of(node)
    return counts


def parent_of(node):
    return node.rpartition("/")[0]


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
