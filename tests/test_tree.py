import os

import pytest

from mash.records import from_box
from mash.tree import Tree


@pytest.fixture
def root(tmp_path):
    return str(tmp_path)


def write(root, relative, text):
    path = os.path.join(root, relative)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def test_loads_records_with_their_node(root):
    write(root, "ssh-prod-web.txt", "ssh prod web -> ssh x\n")
    write(root, "work/k8-ctx.txt", "k8 ctx -> kubectl\n")
    write(root, "work/k8s/ctx-staging.txt", "ctx staging -> kubectl staging\n")
    stored = {s.record.head: s.node for s in Tree(root).load().records}
    assert stored == {
        "ssh prod web": "",
        "k8 ctx": "work",
        "ctx staging": "work/k8s",
    }, "each record should know the node it lives in"


def test_ignores_non_txt_and_dot_folders(root):
    write(root, "keep.txt", "keep -> x\n")
    write(root, "notes.md", "skip -> x\n")
    write(root, ".git/config.txt", "skip too -> x\n")
    write(root, ".journal.log", "2026-01-01\t.\tx\tcopy\n")
    heads = [s.record.head for s in Tree(root).load().records]
    assert heads == ["keep"], "only *.txt outside dot-folders should be records"


def test_missing_root_loads_nothing(tmp_path):
    assert Tree(str(tmp_path / "absent")).load().records == [], "an absent folder is an empty tree"


@pytest.mark.parametrize(
    "node, line, relative",
    [
        ("", "ssh prod web -> ssh x", "ssh-prod-web"),
        ("work", "k8 ctx -> kubectl", "work/k8-ctx"),
        ("work/k8s", "ctx staging -> x", "work/k8s/ctx-staging"),
        ("", "http://127.0.0.1:4000", "http-127-0-0-1-4000"),
    ],
)
def test_add_writes_a_file_named_from_the_head(root, node, line, relative):
    path = Tree(root).add(node, from_box(line))
    stem, _, rest = path[len(root) + 1 :].partition(".")
    assert stem == relative, f"{line!r} in {node!r} should be filed at {relative}.<id>.txt"
    assert rest.endswith(".txt") and len(rest) == 10, "the name ends with a six-char id and .txt"
    with open(path, encoding="utf-8") as f:
        assert f.read() == line + "\n", "the file should hold the record as typed"


def test_add_creates_the_node_on_the_way(root):
    Tree(root).add("a/b/c", from_box("deep -> x"))
    assert os.path.isdir(os.path.join(root, "a", "b", "c")), "missing folders should be created"


def test_add_twice_keeps_both_records(root):
    tree = Tree(root)
    first = tree.add("", from_box("ssh prod web -> one"))
    second = tree.add("", from_box("ssh prod web -> two"))
    assert first != second, "the id keeps the names apart"
    assert len(tree.load().records) == 2, "both records should load"


def test_add_expands_box_newlines_into_lines(root):
    path = Tree(root).add("", from_box("standup -> {{date}};;done: {{done}}"))
    with open(path, encoding="utf-8") as f:
        assert f.read() == "standup -> {{date}}\ndone: {{done}}\n", (
            ";; should be stored as a newline"
        )


def test_delete_removes_the_file(root):
    tree = Tree(root)
    path = tree.add("", from_box("gone -> x"))
    stored = tree.load().records[0]
    tree.delete(stored)
    assert not os.path.exists(path), "delete should remove the record's file"


def test_delete_refuses_when_head_changed_since(root):
    tree = Tree(root)
    path = tree.add("", from_box("gone -> x"))
    stored = tree.load().records[0]
    write(root, os.path.basename(path), "renamed -> x\n")
    with pytest.raises(LookupError):
        tree.delete(stored)
    assert os.path.exists(path), "a file whose head changed should be left alone"


def test_stored_carries_mtime(root):
    path = write(root, "a.txt", "a -> x\n")
    os.utime(path, (1_000_000, 1_000_000))
    stored = Tree(root).load().records[0]
    assert stored.mtime == 1_000_000, "a stored record should carry its file's mtime"


@pytest.fixture
def forest(root):
    write(root, "a.txt", "a -> x\n")
    write(root, "work/b.txt", "b -> x\n")
    write(root, "work/k8s/c.txt", "c -> x\n")
    write(root, "work/k8s/d.txt", "d -> x\n")
    os.makedirs(os.path.join(root, "empty"))
    os.makedirs(os.path.join(root, "work", ".hidden"))
    return Tree(root).load()


def test_snapshot_lists_folders_with_subtree_counts(forest):
    assert forest.folders == {"work": 3, "work/k8s": 2, "empty": 0}, (
        "every folder is listed, empty ones at 0, counts cover the whole subtree"
    )


@pytest.mark.parametrize(
    "node, expected",
    [("", ["empty", "work"]), ("work", ["work/k8s"]), ("work/k8s", []), ("absent", [])],
)
def test_snapshot_children_are_direct_subfolders(forest, node, expected):
    assert forest.children(node) == expected, f"{node!r} should list only its own folders"


@pytest.mark.parametrize(
    "prefix, expected",
    [("w", ["work"]), ("K", ["work/k8s"]), ("e", ["empty"]), ("zzz", [])],
)
def test_snapshot_named_like_matches_the_last_segment(forest, prefix, expected):
    assert forest.named_like(prefix) == expected, f"{prefix!r} should match folder names only"
