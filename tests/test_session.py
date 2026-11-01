"""The shared core: what both surfaces see, with no row format in sight."""

import os

import pytest

from mash.journal import Journal
from mash.records import from_box
from mash.session import Session, Settings
from mash.tree import Tree


@pytest.fixture
def home(tmp_path):
    root = str(tmp_path / "mash")
    tree = Tree(root)
    tree.add("", from_box("ssh prod web -> ssh deploy@10.0.1.5"))
    tree.add("", from_box("ssh box -> ssh {{user=root}}@{{host}}"))
    tree.add("body", from_box("weight kg #body -> 80"))
    tree.add("body", from_box("weight ~> weight kg"))
    tree.add("work/k8s", from_box("ctx staging -> kubectl config use-context staging"))
    os.makedirs(os.path.join(root, "empty"))
    return Session(tree, Journal(os.path.join(root, ".journal.log")), Settings())


def heads(listing):
    return [hit.stored.record.head for hit in listing.hits]


@pytest.mark.parametrize(
    "text, folders",
    [
        ("", [("body", 2), ("empty", 0), ("work", 1)]),
        ("work/", [("work/k8s", 1)]),
        ("w", [("work", 1)]),
        ("work/ c", []),
        ("#body", []),
        ("ssh prod", []),
    ],
)
def test_listing_folders(home, text, folders):
    assert home.listing(text).folders == folders, f"{text!r} should offer exactly these folders"


def test_listing_hits_are_capped_by_max_results(home):
    session = Session(home.tree, home.journal, Settings(max_results=2))
    assert len(session.listing("").hits) == 2, "the cap applies in the core, not the renderer"


@pytest.mark.parametrize(
    "text, run",
    [
        ("ssh prod @kobold", "ssh prod @kobold"),
        ("prod", None),
        ("https://example.com/zzz", None),
        ("ssh prod -> x", None),
    ],
)
def test_listing_offers_to_run_usable_text_only_with_a_hit(home, text, run):
    assert home.listing(text).run == run, f"{text!r}: run only when usable and something matched"


@pytest.mark.parametrize(
    "text, node, new, shown",
    [
        ("stgaing", "", False, "stgaing"),
        ("work/ k8 ctx -> kubectl", "work", False, "k8 ctx -> kubectl"),
        ("empty/ x -> y", "empty", False, "x -> y"),
        ("new/ x -> y", "new", True, "x -> y"),
    ],
)
def test_listing_add_offer(home, text, node, new, shown):
    add = home.listing(text).add
    assert (add.node, add.new, add.text) == (node, new, shown), (
        f"{text!r} should offer to add {shown!r} into {node!r}, new={new}"
    )


def test_add_offer_carries_the_parsed_record(home):
    add = home.listing("k8 => kubernetes").add
    assert add.record.is_rule and add.record.query == "kubernetes", "the offer knows its shape"


def test_prompt_options_in_order_typed_default_clipboard(home, mocker):
    mocker.patch("mash.session.read_clipboard", return_value="10.0.0.9")
    stored = home.listing("box").hits[0].stored
    asked = home.prompt(stored, {}, "")
    assert (asked.name, asked.position, asked.total) == ("user", 1, 2)
    assert [o.value for o in asked.options] == ["root", "10.0.0.9"], "default, then clipboard"
    assert asked.options[0].preview == "ssh root@{{host}}", "the preview fills what is chosen"
    assert all(o.more for o in asked.options), "one blank remains after this one"
    last = home.prompt(stored, {"user": "root"}, "db")
    assert [o.value for o in last.options][:2] == ["db", "10.0.0.9"], "typed text comes first"
    assert last.options[0].values == {"user": "root", "host": "db"}, "values accumulate"
    assert not last.options[0].more, "no blank remains"


def test_touch_chain_touches_every_step_with_the_action(home):
    snapshot = home.tree.load()
    rule = next(s for s in snapshot.records if s.record.is_rule)
    chain = home.resolve_chain(snapshot, rule)
    home.touch_chain(chain.chain, "print")
    touched = home.journal.touched()
    assert set(touched) == {s.identity for s in chain.chain}, "rule and fact, nothing else"
    assert {line[3] for line in home.journal.lines()} == {"print"}, "the action is recorded"


def test_use_touches_after_resolving_and_reports_the_chain(home, mocker):
    perform = mocker.patch("mash.session.actions.perform")
    rule = next(s for s in home.tree.load().records if s.record.is_rule)
    assert home.use(rule, "copy", {}) == "weight → weight kg #body → 80"
    assert perform.call_args[0][0].target == "80", "the fact's body is what gets copied"
    assert len(home.journal.touched()) == 2, "the chain was touched"


def test_use_with_blanks_left_does_not_touch(home, mocker):
    mocker.patch("mash.session.read_clipboard", return_value="")
    box = home.listing("box").hits[0].stored
    assert home.use(box, "copy", {}) == "Fill in the blanks first"
    assert not home.journal.touched(), "nothing happened, so nothing was touched"


def test_forget_history_keeps_the_record(home):
    stored = home.listing("prod").hits[0].stored
    home.journal.touch(stored.identity, "copy")
    assert home.forget_history(stored) == "Forgot history of: ssh prod web"
    assert stored.identity not in home.journal.touched(), "its lines are gone"
    assert heads(home.listing("prod")) == ["ssh prod web"], "the record is still there"
