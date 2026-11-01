"""What a touch is, and what it does to the time axis.

A touch is any use of a record: ↩ on it, ⇧↩, adding it, printing it from the CLI, and
every step a rule resolution walks through, the fact it lands on included. The time axis
orders by last touch, so using a record moves it to the front.
"""

import json
import time

import pytest

from mash import alfred
from mash.journal import Journal
from mash.session import Session, Settings
from mash.tree import Tree


@pytest.fixture
def home(tmp_path, mocker):
    mocker.patch("mash.session.actions.perform")
    start = time.time() + 1
    clock = iter(start + t for t in range(10_000))
    mocker.patch("mash.journal.now", side_effect=lambda: next(clock))
    tree = Tree(str(tmp_path))
    session = Session(tree, Journal(str(tmp_path / ".journal.log")), Settings())
    session.add("body", "weight kg #body -> 80")
    session.add("body", "weight kg #body -> 79")
    session.add("body", "oldest ~> weight kg")
    session.add("body", "newest => weight kg")
    return session


def first(session, text):
    return alfred.items(session, text)["items"][0]


def press(session, text):
    return alfred.act(session, json.loads(first(session, text)["arg"]))


def test_adding_is_a_touch_so_the_last_added_is_newest(home):
    assert first(home, "weight kg")["subtitle"] == "79", "79 was added after 80"
    assert press(home, "newest") == "newest → weight kg #body → 79"
    assert press(home, "oldest") == "oldest → weight kg #body → 80"


def test_resolving_touches_the_fact_it_lands_on(home):
    before = dict(home.journal.touched())
    press(home, "oldest")
    after = home.journal.touched()
    moved = [i for i in after if after[i] != before.get(i)]
    assert len(moved) == 2, "the rule and the fact it reached were touched, nothing else"


def test_after_oldest_the_same_record_is_also_newest(home):
    assert press(home, "oldest") == "oldest → weight kg #body → 80"
    assert press(home, "newest") == "newest → weight kg #body → 80", (
        "80 was just used, so it is now the most recently touched weight"
    )
    assert press(home, "oldest") == "oldest → weight kg #body → 79", (
        "and 79, untouched since it was added, is now the oldest"
    )


def test_browsing_the_list_is_not_a_touch(home):
    before = dict(home.journal.touched())
    home.listing("")
    home.listing("weight")
    assert home.journal.touched() == before, "listing never writes the journal"


def test_pressing_a_fact_directly_touches_only_that_fact(home):
    before = dict(home.journal.touched())
    press(home, "weight kg")
    after = home.journal.touched()
    assert sum(after[i] != before.get(i) for i in after) == 1, "one record, one touch"


def test_forgetting_history_makes_a_record_oldest_by_mtime(home):
    press(home, "oldest")
    identity = home.tree.read(json.loads(first(home, "weight kg")["arg"])["path"]).identity
    home.forget_history(home.tree.read(json.loads(first(home, "weight kg")["arg"])["path"]))
    assert identity not in home.journal.touched(), "its history is gone"
    assert press(home, "oldest") == "oldest → weight kg #body → 80", (
        "with no journal lines it falls back to its file mtime, which is the oldest"
    )
