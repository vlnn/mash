"""The manual that ships in help/: every record is checked, and so is its place in the bundle."""

import importlib.util
import json
import os

import pytest

from mash import actions, alfred, cli, fill
from mash.journal import Journal
from mash.session import Session, Settings
from mash.tree import ID_LENGTH, Tree

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOPICS = [
    "add",
    "blanks",
    "fish",
    "journal",
    "keys",
    "nodes",
    "records",
    "rules",
    "search",
    "setup",
    "start",
]

LOOKUPS = [
    ("help/ start", "start here"),
    ("help/ delete", "opt-enter delete"),
    ("help/ paste", "shift-enter paste"),
    ("help/ edit", "cmd-enter edit"),
    ("help/ tilde", "tilde in an arrow"),
    ("help/ queue", "how to make a queue"),
    ("help/ synonym", "synonym rule"),
    ("help/ blank default", "default for a blank"),
    ("help/ tag prefix", "tag prefix rule"),
    ("help/ semicolons", "multi-line body in the alfred box"),
    ("help/ id", "record id"),
    ("help/ index", "what is the index"),
    ("help/ stash", "stash in fish"),
    ("help/ secrets", "secrets"),
    ("help/ whole", "score whole head word"),
    ("help/search/ order", "order of results"),
    ("help/journal/ not", "what is not a touch"),
    ("help/ kctx", "why kctx misses k8s ctx"),
    ("help/ undo", "opt-enter delete"),
    ("help/ pbcopy", "pipes"),
]


@pytest.fixture
def home(tmp_path, mocker):
    mocker.patch("mash.session.actions.perform")
    mocker.patch("mash.session.read_clipboard", return_value="")
    root = str(tmp_path / "mash")
    return Session(
        Tree(root, mounts={"help": cli.MANUAL}), Journal(os.path.join(root, ".j")), Settings()
    )


def shipped():
    return sorted(Tree("", mounts={"help": cli.MANUAL}).load().records, key=lambda s: s.path)


def shipped_facts():
    return [s for s in shipped() if not s.record.is_rule]


def label(stored):
    return f"{stored.node}/{stored.record.head}"


def heads(listing):
    return [hit.stored.record.head for hit in listing.hits]


def press(session, text):
    rows = alfred.items(session, text)["items"]
    return alfred.act(session, json.loads(next(row["arg"] for row in rows if "arg" in row)))


def build_script():
    spec = importlib.util.spec_from_file_location(
        "build", os.path.join(REPO, "scripts", "build.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_manual_is_there():
    assert len(shipped()) > 100, "help/ ships more than a hundred records"


def test_the_manual_is_a_folder_per_topic(home):
    assert [node for node, _ in home.listing("help/").folders] == [f"help/{t}" for t in TOPICS], (
        "m help/ offers one folder per topic"
    )


@pytest.mark.parametrize("stored", shipped(), ids=label)
def test_every_shipped_record_was_written_by_mash(stored):
    assert len(stored.identity) == ID_LENGTH, f"{stored.path} should carry an id"
    assert not stored.record.tags, f"{stored.record.head!r} should not grow a tag by accident"
    assert "\n" not in stored.record.body, "one line, so the subtitle and the banner show it whole"


@pytest.mark.parametrize("stored", shipped_facts(), ids=label)
def test_every_shipped_fact_is_safe_to_reach_through_a_rule(stored):
    body = fill.fill(stored.record.body, {}, str)
    assert not fill.blanks(body), f"{stored.record.head!r} should have a default for every blank"
    assert actions.decide(body, lambda path: True, {}) == actions.Action("copy", body), (
        f"enter on {stored.record.head!r} should copy, never open or hand off"
    )


@pytest.mark.parametrize("text, head", LOOKUPS)
def test_looking_something_up_in_the_manual(home, text, head):
    assert heads(home.listing(text))[:1] == [head], f"m {text} should put {head!r} first"


def test_the_manual_never_shows_without_help(home):
    assert heads(home.listing("")) == [], "a bare m on an empty tree lists no manual record"
    assert heads(home.listing("score")) == [], "and neither does a word the manual is full of"


def test_the_quiz_goes_round_the_whole_manual(home):
    others = len(shipped()) - 1
    served = [press(home, "help/ quiz").split(" → ")[1] for _ in range(others)]
    assert len(set(served)) == others, "each press hands out a record not seen yet in this round"
    assert "quiz" not in served, "and never the quiz itself"


def test_the_bundle_carries_the_manual():
    bundled = set(build_script().files())
    missing = [s.path for s in shipped() if os.path.relpath(s.path, REPO) not in bundled]
    assert not missing, f"scripts/build.py should bundle every help record, missing {missing[:3]}"
