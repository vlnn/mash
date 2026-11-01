import os
import pickle

from mash.records import from_box
from mash.tree import INDEX, Tree


def heads(tree):
    return sorted(s.record.head for s in tree.load().records)


def test_index_file_appears_after_first_load(tmp_path):
    tree = Tree(str(tmp_path))
    tree.add("", from_box("a -> 1"))
    tree.load()
    assert (tmp_path / INDEX).exists(), "the first load writes the index"


def test_second_load_does_not_reparse_unchanged_files(tmp_path, mocker):
    tree = Tree(str(tmp_path))
    tree.add("", from_box("a -> 1"))
    tree.add("work", from_box("b -> 2"))
    tree.load()
    parse = mocker.spy(__import__("mash.tree", fromlist=["read_record"]), "read_record")
    assert heads(Tree(str(tmp_path))) == ["a", "b"], "a fresh Tree reads the same records"
    assert parse.call_count == 0, "nothing changed, nothing is parsed"


def test_changed_file_is_reparsed(tmp_path):
    tree = Tree(str(tmp_path))
    path = tree.add("", from_box("a -> 1"))
    tree.load()
    with open(path, "w", encoding="utf-8") as f:
        f.write("a -> 2\n")
    os.utime(path, (2_000_000_000, 2_000_000_000))
    assert Tree(str(tmp_path)).load().records[0].record.body == "2", "a newer mtime means reparse"


def test_deleted_file_leaves_the_index(tmp_path):
    tree = Tree(str(tmp_path))
    path = tree.add("", from_box("a -> 1"))
    tree.add("", from_box("b -> 2"))
    tree.load()
    os.remove(path)
    assert heads(Tree(str(tmp_path))) == ["b"], "a removed file is gone on the next load"


def test_index_is_rewritten_only_when_something_changed(tmp_path):
    tree = Tree(str(tmp_path))
    tree.add("", from_box("a -> 1"))
    tree.load()
    index = tmp_path / INDEX
    os.utime(index, (1_000, 1_000))
    Tree(str(tmp_path)).load()
    assert os.stat(index).st_mtime == 1_000, "an unchanged tree leaves the index alone"
    tree.add("", from_box("b -> 2"))
    Tree(str(tmp_path)).load()
    assert os.stat(index).st_mtime != 1_000, "a new record rewrites it"


def test_corrupt_index_is_ignored(tmp_path):
    tree = Tree(str(tmp_path))
    tree.add("", from_box("a -> 1"))
    (tmp_path / INDEX).write_bytes(b"garbage")
    assert heads(tree) == ["a"], "a broken index falls back to parsing"


def test_index_from_another_version_is_ignored(tmp_path):
    tree = Tree(str(tmp_path))
    tree.add("", from_box("a -> 1"))
    (tmp_path / INDEX).write_bytes(pickle.dumps(("v-1", {})))
    assert heads(tree) == ["a"], "an old index format falls back to parsing"
