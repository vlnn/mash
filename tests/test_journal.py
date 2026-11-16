import os

import pytest

from mash.journal import COMPACT_AT, Journal


@pytest.fixture
def journal(tmp_path):
    return Journal(str(tmp_path / ".journal.log"))


def test_touch_appends_a_tab_separated_line(journal, mocker):
    mocker.patch("mash.journal.now", return_value=1_700_000_000.0)
    journal.touch("a1b2c3", "copy", "work/k8s")
    with open(journal.path, encoding="utf-8") as f:
        assert f.read() == "1700000000.000\ta1b2c3\twork/k8s\tcopy\n", (
            "a touch is time, identity, node, action"
        )


def test_root_node_is_written_as_a_dot(journal):
    journal.touch("a1b2c3", "resolve")
    with open(journal.path, encoding="utf-8") as f:
        assert f.read().split("\t")[2] == ".", "the root node should be spelled ."


def test_touched_maps_identity_to_last_time(journal, mocker):
    clock = mocker.patch("mash.journal.now", side_effect=[10.0, 20.0, 30.0])
    journal.touch("a", "copy")
    journal.touch("b", "copy", "body")
    journal.touch("a", "copy")
    assert journal.touched() == {"a": 30.0, "b": 20.0}, "touched keeps the latest time per record"
    assert clock.call_count == 3, "each touch reads the clock once"


def test_missing_journal_is_empty(journal):
    assert journal.touched() == {}, "no journal file means nothing was touched"


def test_bad_lines_are_skipped(journal):
    with open(journal.path, "w", encoding="utf-8") as f:
        f.write("garbage\n\n10\ta\t.\tcopy\nnot-a-time\tb\t.\tcopy\n")
    assert journal.touched() == {"a": 10.0}, "unreadable lines should be ignored"


def test_two_touches_in_one_second_keep_their_order(journal, mocker):
    mocker.patch("mash.journal.now", side_effect=[5.001, 5.002])
    journal.touch("first", "add")
    journal.touch("second", "add")
    touched = journal.touched()
    assert touched["second"] > touched["first"], "stamps keep milliseconds"


def test_forget_drops_every_line_of_a_record(journal):
    journal.touch("a", "copy")
    journal.touch("b", "copy")
    journal.touch("a", "paste")
    journal.forget("a")
    assert list(journal.touched()) == ["b"], "forget should leave only other records"


def test_forget_node_drops_its_subtree(journal):
    journal.touch("a", "copy", "work")
    journal.touch("b", "copy", "work/k8s")
    journal.touch("c", "copy", "workshop")
    journal.forget_node("work")
    assert list(journal.touched()) == ["c"], (
        "forgetting a node should drop it and its children but not look-alikes"
    )


def test_compacts_past_the_threshold(journal, mocker):
    mocker.patch("mash.journal.now", side_effect=iter(range(COMPACT_AT + 2)))
    for _ in range(COMPACT_AT + 1):
        journal.touch("a", "copy", "body")
    with open(journal.path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    assert len(lines) == 1, "the journal should compact to one line per record"
    assert lines[0].split("\t")[2:] == ["body", f"touched x{COMPACT_AT + 1}"], (
        "the compacted line keeps the node and carries the count"
    )
    assert journal.touched() == {"a": float(COMPACT_AT)}, "the latest time survives compaction"


def test_journal_is_a_dotfile(journal):
    journal.touch("a", "copy")
    assert os.path.basename(journal.path).startswith("."), "the journal hides from the tree walk"


@pytest.mark.parametrize(
    "actions, count",
    [
        (["add"], 1),
        (["add", "copy", "paste"], 3),
        (["touched x4"], 4),
        (["touched x4", "copy"], 5),
        (["touched xmany"], 1),
    ],
)
def test_uses_counts_touches_through_compaction(journal, mocker, actions, count):
    mocker.patch("mash.journal.now", side_effect=range(10, 10 + len(actions)))
    for action in actions:
        journal.touch("a", action)
    assert journal.uses()["a"] == (count, 9.0 + len(actions)), (
        f"{actions} should count as {count} uses, the last one at the last stamp"
    )
