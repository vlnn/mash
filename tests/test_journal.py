import os

import pytest

from mash.journal import COMPACT_AT, Journal


@pytest.fixture
def journal(tmp_path):
    return Journal(str(tmp_path / ".journal.log"))


def test_touch_appends_a_tab_separated_line(journal, mocker):
    mocker.patch("mash.journal.now", return_value=1_700_000_000.0)
    journal.touch("work/k8s", "k8 ctx", "copy")
    with open(journal.path, encoding="utf-8") as f:
        assert f.read() == "1700000000\twork/k8s\tk8 ctx\tcopy\n", (
            "a touch should be one tab-separated line"
        )


def test_root_node_is_written_as_a_dot(journal):
    journal.touch("", "weight", "resolve")
    with open(journal.path, encoding="utf-8") as f:
        assert f.read().split("\t")[1] == ".", "the root node should be spelled ."


def test_touched_maps_identity_to_last_time(journal, mocker):
    clock = mocker.patch("mash.journal.now", side_effect=[10.0, 20.0, 30.0])
    journal.touch("", "a", "copy")
    journal.touch("body", "b", "copy")
    journal.touch("", "a", "copy")
    assert journal.touched() == {("", "a"): 30.0, ("body", "b"): 20.0}, (
        "touched should keep the latest time per record"
    )
    assert clock.call_count == 3, "each touch reads the clock once"


def test_missing_journal_is_empty(journal):
    assert journal.touched() == {}, "no journal file means nothing was touched"


def test_bad_lines_are_skipped(journal):
    with open(journal.path, "w", encoding="utf-8") as f:
        f.write("garbage\n\n10\t.\ta\tcopy\nnot-a-time\t.\tb\tcopy\n")
    assert journal.touched() == {("", "a"): 10.0}, "unreadable lines should be ignored"


def test_forget_drops_every_line_of_a_record(journal):
    journal.touch("", "a", "copy")
    journal.touch("", "b", "copy")
    journal.touch("", "a", "paste")
    journal.forget("", "a")
    assert list(journal.touched()) == [("", "b")], "forget should leave only other records"


def test_forget_node_drops_its_subtree(journal):
    journal.touch("work", "a", "copy")
    journal.touch("work/k8s", "b", "copy")
    journal.touch("workshop", "c", "copy")
    journal.forget_node("work")
    assert list(journal.touched()) == [("workshop", "c")], (
        "forgetting a node should drop it and its children but not look-alikes"
    )


def test_compacts_past_the_threshold(journal, mocker):
    mocker.patch("mash.journal.now", side_effect=iter(range(COMPACT_AT + 2)))
    for _ in range(COMPACT_AT + 1):
        journal.touch("", "a", "copy")
    with open(journal.path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    assert len(lines) == 1, "the journal should compact to one line per record"
    assert lines[0].split("\t")[3] == f"touched x{COMPACT_AT + 1}", (
        "the compacted line should carry the count"
    )
    assert journal.touched() == {("", "a"): float(COMPACT_AT)}, (
        "the latest time should survive compaction"
    )


def test_compaction_keeps_file_a_dotfile(journal):
    journal.touch("", "a", "copy")
    assert os.path.basename(journal.path).startswith("."), "the journal hides from the tree walk"
