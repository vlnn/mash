"""A read-only tree mounted at a node: found only when the node is named, never written to."""

import json
import os

import pytest

from mash import alfred
from mash.journal import Journal
from mash.records import from_box
from mash.session import Session, Settings
from mash.tree import Tree

SHIPPED = [
    ("", "start here -> type help/ and a word"),
    ("", "quiz ~> help/"),
    ("keys", "enter key -> copies, opens or hands off"),
    ("keys", "shift enter key -> pastes"),
    ("keys", "newest => enter"),
]
OWN = [
    ("", "enter the office -> code 4821"),
    ("work", "ssh prod web -> ssh deploy@10.0.1.5"),
]


@pytest.fixture
def manual(tmp_path):
    tree = Tree(str(tmp_path / "manual"))
    for node, line in SHIPPED:
        tree.add(node, from_box(line))
    return tree.root


@pytest.fixture
def root(tmp_path):
    return str(tmp_path / "mash")


@pytest.fixture
def home(root, manual, mocker):
    mocker.patch("mash.session.actions.perform")
    session = Session(
        Tree(root, mounts={"help": manual}), Journal(os.path.join(root, ".journal.log")), Settings()
    )
    for node, line in OWN:
        session.tree.add(node, from_box(line))
    return session


def heads(listing):
    return [hit.stored.record.head for hit in listing.hits]


def stored_by_head(session, head):
    return next(s for s in session.tree.load().records if s.record.head == head)


def files_under(folder):
    return sorted(name for _, _, names in os.walk(folder) for name in names)


def press(session, text):
    rows = alfred.items(session, text)["items"]
    return alfred.act(session, json.loads(next(row["arg"] for row in rows if "arg" in row)))


def test_mounted_records_load_under_the_mount_node(home):
    nodes = {s.record.head: (s.node, s.shipped) for s in home.tree.load().records}
    assert nodes == {
        "start here": ("help", True),
        "quiz": ("help", True),
        "enter key": ("help/keys", True),
        "shift enter key": ("help/keys", True),
        "newest": ("help/keys", True),
        "enter the office": ("", False),
        "ssh prod web": ("work", False),
    }, "shipped records sit under help/, and only they are marked shipped"


def test_the_mount_and_its_folders_are_nodes(home):
    assert home.tree.load().folders == {"help": 5, "help/keys": 3, "work": 1}, (
        "help/ counts its whole subtree, like any node"
    )


@pytest.mark.parametrize(
    "text, found",
    [
        ("", ["ssh prod web", "enter the office"]),
        ("enter", ["enter the office"]),
        ("shift", []),
        ("work/ enter", []),
        ("help/ enter", ["enter key", "shift enter key"]),
        ("help/ shift", ["shift enter key"]),
        ("help/keys/", ["enter key", "shift enter key", "newest"]),
        ("help/ keys/ shift", ["shift enter key"]),
    ],
)
def test_shipped_records_are_found_only_when_their_node_is_named(home, text, found):
    assert sorted(heads(home.listing(text))) == sorted(found), (
        f"m {text} should find exactly {found}"
    )


def test_browsing_the_mount_lists_everything_in_it(home):
    assert sorted(heads(home.listing("help/"))) == sorted(
        from_box(line).head for _, line in SHIPPED
    ), "m help/ lists the whole manual"


@pytest.mark.parametrize(
    "text, folders",
    [
        ("", [("help", 5), ("work", 1)]),
        ("he", [("help", 5)]),
        ("help/", [("help/keys", 3)]),
    ],
)
def test_the_mount_shows_as_a_folder_row(home, text, folders):
    assert home.listing(text).folders == folders, f"m {text} should offer {folders}"


def test_reading_a_shipped_path_knows_its_node(home):
    path = stored_by_head(home, "enter key").path
    stored = home.tree.read(path)
    assert (stored.node, stored.shipped) == ("help/keys", True), (
        "a path inside the mount reads back under help/ and as shipped"
    )


def test_a_shipped_record_cannot_be_deleted(home, manual):
    before = files_under(manual)
    message = home.delete(stored_by_head(home, "enter key"))
    assert message == "Not deleted: enter key is part of mash's manual", "the answer says why"
    assert files_under(manual) == before, "and the file is still there"


def test_alt_enter_on_a_shipped_row_is_switched_off(home):
    row = alfred.items(home, "help/ shift")["items"][0]
    assert row["mods"]["alt"] == {
        "valid": False,
        "subtitle": "Part of mash's manual: cannot be deleted",
    }, "the row says it cannot be deleted instead of offering to"


def test_adding_under_the_mount_node_writes_to_your_own_tree(home, root, manual):
    before = files_under(manual)
    assert home.add("help", "my own note -> remember this") == "Added to help/: my own note"
    assert files_under(manual) == before, "nothing is written into the mount"
    stored = stored_by_head(home, "my own note")
    assert stored.path.startswith(os.path.join(root, "help")), "it lands in your tree's help/"
    assert not stored.shipped, "so it is yours"
    assert heads(home.listing("own note")) == ["my own note"], "and is found from anywhere"


def test_loading_never_writes_into_the_mount(home, manual):
    before = files_under(manual)
    home.listing("help/")
    home.listing("help/")
    assert files_under(manual) == before, "no index and no journal appear in the mount"


def test_the_mount_works_before_your_tree_exists(root, manual):
    session = Session(Tree(root, mounts={"help": manual}), Journal(root + "/.j"), Settings())
    assert heads(session.listing("help/ shift")) == ["shift enter key"], "the manual is there"
    assert not os.path.exists(root), "and looking at it creates nothing"


def test_using_the_mount_before_your_tree_exists_starts_your_journal(root, manual, mocker):
    mocker.patch("mash.session.actions.perform")
    journal = Journal(os.path.join(root, ".journal.log"))
    session = Session(Tree(root, mounts={"help": manual}), journal, Settings())
    assert press(session, "help/ shift") == "Copied: pastes", "enter works on a first run"
    assert len(journal.touched()) == 1, "and the touch is kept, which creates your folder"


def test_using_a_shipped_record_moves_it_up(home):
    assert press(home, "help/ shift") == "Copied: pastes"
    assert heads(home.listing("help/keys/"))[0] == "shift enter key", (
        "a touch is journaled for shipped records too"
    )


@pytest.mark.parametrize(
    "node, rule, typed, message",
    [
        ("", "review ~> help/keys/", "review", "review → enter key → copies, opens or hands off"),
        ("", "paste => help/ shift", "paste", "paste → shift enter key → pastes"),
        ("", "door => enter", "door", "door → enter the office → code 4821"),
        ("", "missing => shift", "missing", "Could not resolve: nothing matches 'shift'"),
    ],
)
def test_your_rules_reach_the_mount_only_by_naming_it(home, node, rule, typed, message):
    home.tree.add(node, from_box(rule))
    assert press(home, typed) == message, f"{rule!r} should answer {message!r}"


def test_a_shipped_rule_searches_its_own_folder_in_the_mount(home):
    assert press(home, "help/ newest") == "newest → enter key → copies, opens or hands off", (
        "a rule in help/keys/ finds the shipped record beside it, not your enter the office"
    )


def test_a_queue_over_the_mount_never_hands_out_itself(home):
    served = [press(home, "help/ quiz").split(" → ")[1] for _ in range(4)]
    assert "quiz" not in served, "the rule is not one of its own candidates"
    assert set(served) == {"start here", "enter key", "shift enter key", "newest"}, (
        "four presses hand out the four other shipped records"
    )
