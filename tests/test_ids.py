import os
import re

from mash.records import from_box
from mash.tree import Tree, identity_of, new_id


def test_new_ids_are_short_lowercase_and_distinct():
    ids = {new_id() for _ in range(200)}
    assert len(ids) == 200, "ids should not collide in practice"
    assert all(re.fullmatch(r"[a-z0-9]{6}", i) for i in ids), "an id is six lowercase alphanumerics"


def test_add_puts_the_id_in_the_file_name(tmp_path):
    path = Tree(str(tmp_path)).add("", from_box("ssh prod web -> x"))
    assert re.fullmatch(r"ssh-prod-web\.[a-z0-9]{6}\.txt", os.path.basename(path)), (
        "the file is slug.id.txt"
    )


def test_same_head_twice_gives_two_records_with_their_own_ids(tmp_path):
    tree = Tree(str(tmp_path))
    tree.add("", from_box("weight kg -> 80"))
    tree.add("", from_box("weight kg -> 79"))
    stored = tree.load().records
    assert len({s.identity for s in stored}) == 2, "identities differ"
    assert {s.record.body for s in stored} == {"80", "79"}, "both records are there"


def test_identity_is_the_id_when_the_name_carries_one():
    assert identity_of("work/k8s", "k8-ctx.a1b2c3") == "a1b2c3", (
        "the id alone identifies the record"
    )


def test_hand_made_file_without_id_is_identified_by_its_place():
    assert identity_of("work", "notes") == "work/notes", "no id: node and file name"
    assert identity_of("", "notes") == "notes", "root records are just the name"


def test_renaming_the_slug_keeps_the_identity(tmp_path):
    tree = Tree(str(tmp_path))
    path = tree.add("", from_box("old head -> x"))
    before = tree.load().records[0].identity
    os.rename(path, path.replace("old-head", "new-head"))
    assert tree.load().records[0].identity == before, "the id survives a rename that keeps it"


def test_moving_between_nodes_keeps_the_identity(tmp_path):
    tree = Tree(str(tmp_path))
    path = tree.add("", from_box("moved -> x"))
    before = tree.load().records[0].identity
    os.makedirs(tmp_path / "work")
    os.rename(path, str(tmp_path / "work" / os.path.basename(path)))
    assert tree.load().records[0].identity == before, "the id survives a move"
