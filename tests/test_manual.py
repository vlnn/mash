"""docs/MANUAL.md, checked: every example it shows is run here against a copy of examples/."""

import itertools
import json
import os
import shutil

import pytest

from mash import actions, alfred, cli, fill
from mash.journal import Journal
from mash.session import Session, Settings
from mash.tree import ID_LENGTH, Tree

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES = os.path.join(REPO, "examples")
MANUAL = os.path.join(REPO, "docs", "MANUAL.md")
FLOWS = {"books": "bk"}
AFTER_THE_SAMPLE_HISTORY = 1_800_000_000
BUILT_IN = {"help": cli.MANUAL}
MANUAL_SIZE = len(Tree("", mounts=BUILT_IN).walk()[1])

STAGING_AND_PROD_SSH = ["ssh staging web", "ssh prod web"]
PROD_AND_STAGING_CTX = ["k8s ctx prod kube", "k8s ctx staging kube"]
READING = ["book snow crash #reading", "paper attention #reading #ml"]

SEARCHES = [
    ("prod", ["ssh prod web", "k8s ctx prod kube"]),
    ("web ssh", STAGING_AND_PROD_SSH),
    ("stg", ["ssh staging web", "k8s ctx staging kube", "wifi guest"]),
    ("k8 prd", ["k8s ctx prod kube"]),
    ("grf lat", ["grafana api latency"]),
    ("кав", ["кава coffee order"]),
    ("deploy", STAGING_AND_PROD_SSH),
    ("dply", STAGING_AND_PROD_SSH),
    ("use-context", PROD_AND_STAGING_CTX),
    ("ssh prod staging", []),
    ("kctx", []),
    ("k ctx", PROD_AND_STAGING_CTX),
    ("stgaing", []),
    ("stgng", ["ssh staging web", "k8s ctx staging kube"]),
    ("algorithms @books", ["algorithms book"]),
    ("work/ ctx", PROD_AND_STAGING_CTX),
    ("work/k8s/ ctx", PROD_AND_STAGING_CTX),
    ("work/ k8s/ ctx", PROD_AND_STAGING_CTX),
    ("home/chores/", ["descale kettle", "take out recycling", "water plants"]),
    ("wifi", ["wifi guest", "wifi office"]),
    ("#reading", READING),
    ("#read", ["book dune #read", *READING]),
    ("#ml #reading", ["paper attention #reading #ml"]),
    ("#reading snow", ["book snow crash #reading"]),
    ("paper", ["paper sizes", "paper adam optimizer #ml", "paper attention #reading #ml"]),
    ("weight", ["weight", "weight now", "weight kg #body", "weight kg #body"]),
    ("delete", []),
    ("help/ delete", ["opt-enter delete", "what is the index"]),
    ("help/ tilde", ["tilde in an arrow"]),
    ("help/keys/ paste", ["shift-enter paste", "banner after enter"]),
    ("size", ["shoe size", "photo sizes", "paper sizes"]),
    ("a4", ["paper sizes"]),
    ("e27", ["bulbs"]),
    ("443", ["ports"]),
    ("755", ["chmod modes"]),
    ("tbsp", ["cup spoon ml"]),
    ("home/recipes/", ["cup spoon ml", "oven temps", "pancakes"]),
]

FOLDERS = [
    ("", [("body", 4), ("help", MANUAL_SIZE), ("home", 18), ("work", 17)]),
    ("wo", [("work", 17)]),
    ("work/", [("work/cli", 6), ("work/k8s", 3)]),
    ("home/", [("home/chores", 3), ("home/recipes", 3)]),
    ("chore", [("home/chores", 3)]),
    ("work/ ctx", []),
]

ARROWS = [
    ("weight kg", ["79", "80"]),
    ("~> weight kg", ["80", "79"]),
]

RULES = [
    ("dashboard", "dashboard → grafana api latency → https://grafana.example.com/d/api-latency"),
    ("reading now", "reading now → book snow crash #reading → Stephenson, 1992"),
    ("latest ml", "latest ml #ml → paper adam optimizer #ml → https://arxiv.org/abs/1412.6980"),
    ("work/ net", "net → wifi office → CorpNet-5G"),
    ("home/ net", "net → wifi guest → GuestNetwork-5G"),
    ("weight now", "weight now → weight kg #body → 79"),
    ("weight", "weight → weight kg #body → 80"),
]

PRESSES = [
    ("ssh prod web", "copy", "ssh deploy@10.0.1.5"),
    ("grafana api latency", "open", "https://grafana.example.com/d/api-latency"),
    ("downloads folder", "open", os.path.expanduser("~/Downloads")),
    ("algorithms book", "handoff", "bk algorithms"),
    ("quick note", "handoff", "n"),
    ("email work", "copy", "name.surname@example.com"),
    ("bins go out on thursday", "copy", "bins go out on thursday"),
]

OFFERS = [
    ("stgaing", "", False, "stgaing"),
    ("work/ k8s/ ctx dev", "work/k8s", False, "ctx dev"),
    ("garden/ tomatoes sown", "garden", True, "tomatoes sown"),
    ("home/ wifi cafe -> CafeNet", "home", False, "wifi cafe -> CafeNet"),
]

TYPED = [text for text, _ in itertools.chain(SEARCHES, FOLDERS, ARROWS, RULES)]


@pytest.fixture
def sample(tmp_path, mocker):
    mocker.patch("mash.session.actions.perform")
    clock = itertools.count(AFTER_THE_SAMPLE_HISTORY)
    mocker.patch("mash.journal.now", side_effect=lambda: float(next(clock)))
    folder = str(tmp_path / "mash")
    shutil.copytree(EXAMPLES, folder)
    journal = Journal(os.path.join(folder, ".journal.log"))
    return Session(Tree(folder, mounts=BUILT_IN), journal, Settings(flows=FLOWS))


@pytest.fixture(scope="module")
def manual():
    with open(MANUAL, encoding="utf-8") as f:
        return f.read()


def sample_files():
    return sorted(os.path.relpath(entry.path, EXAMPLES) for _, entry in Tree(EXAMPLES).walk()[1])


def first_line(path):
    with open(path, encoding="utf-8") as f:
        return f.readline().rstrip("\n")


def heads(listing):
    return [hit.stored.record.head for hit in listing.hits]


def bodies(listing):
    return [hit.stored.record.body for hit in listing.hits]


def by_head(session, head):
    return next(s.record for s in session.tree.load().records if s.record.head == head)


def press(session, text):
    rows = alfred.items(session, text)["items"]
    return alfred.act(session, json.loads(next(row["arg"] for row in rows if "arg" in row)))


@pytest.mark.parametrize("text, found", SEARCHES)
def test_searching_the_sample_tree(sample, text, found):
    assert heads(sample.listing(text)) == found, f"m {text} should list exactly {found}"


@pytest.mark.parametrize("text, folders", FOLDERS)
def test_folder_rows(sample, text, folders):
    assert sample.listing(text).folders == folders, f"m {text} should offer the folders {folders}"


@pytest.mark.parametrize("text, values", ARROWS)
def test_an_arrow_on_the_query_reverses_the_time_tiebreak(sample, text, values):
    assert bodies(sample.listing(text)) == values, f"m {text} should list the weights as {values}"


@pytest.mark.parametrize("text, chain", RULES)
def test_pressing_a_rule_shows_its_chain(sample, text, chain):
    assert press(sample, text) == chain, f"m {text} ↩ should resolve as {chain}"


def test_a_queue_rule_hands_out_the_chores_in_turn(sample):
    served = [press(sample, "next chore").split(" → ")[-1] for _ in range(4)]
    assert served == ["water plants", "take out recycling", "descale kettle", "water plants"], (
        "each ↩ touches the chore it returns, so the next ↩ returns the one waiting longest"
    )


def test_reading_through_a_rule_is_a_use(sample):
    values = [press(sample, text).split(" → ")[-1] for text in ("weight", "weight now", "weight")]
    assert values == ["80", "80", "79"], (
        "weight ↩ touches the 80, so weight now returns it too, and weight then finds the 79"
    )


@pytest.mark.parametrize("head, kind, target", PRESSES)
def test_what_enter_does(sample, head, kind, target):
    action = actions.decide(by_head(sample, head).body, lambda path: True, FLOWS)
    assert action == actions.Action(kind, target), f"↩ on {head!r} should {kind} {target!r}"


def test_run_row_for_a_typed_hand_off(sample):
    assert sample.listing("algorithms @books").run == "algorithms @books", (
        "a typed hand-off that found something is offered as Run"
    )


@pytest.mark.parametrize("text, node, new, shown", OFFERS)
def test_add_offer(sample, text, node, new, shown):
    offer = sample.listing(text).add
    assert (offer.node, offer.new, offer.text) == (node, new, shown), (
        f"m {text} should offer to add {shown!r} to {node or 'the root'}"
    )


def test_a_miss_is_one_enter_from_being_stored(sample):
    assert heads(sample.listing("tomato")) == [], "nothing in the sample is about tomatoes"
    assert sample.add("garden", "tomatoes sown") == "Added to garden/: tomatoes sown", (
        "adding says where the record went"
    )
    assert heads(sample.listing("tomato")) == ["tomatoes sown"], "and the next search finds it"


def test_adding_what_is_already_there_stores_nothing(sample):
    before = len(sample.tree.load().records)
    assert sample.add("home", "wifi guest -> GuestNetwork-5G") == "Already there: wifi guest", (
        "the sample already holds this record in home/"
    )
    assert len(sample.tree.load().records) == before, "so no second file is written"
    assert heads(sample.listing("wifi")) == ["wifi guest", "wifi office"], "and it stays one row"


def test_blanks_are_asked_in_order_with_their_defaults(sample):
    body = by_head(sample, "ssh box").body
    assert fill.blanks(body) == [("user", "root"), ("host", None), ("port", "22")], (
        "ssh box asks for user, host and port, two of them with defaults"
    )
    assert fill.fill(body, {"user": "deploy", "host": "db.example.com"}, str) == (
        "ssh deploy@db.example.com -p 22"
    ), "an unanswered blank falls back to its default"


def test_a_multi_line_body_is_stored_verbatim(sample, mocker):
    mocker.patch("mash.fill.today", return_value="2026-11-14")
    assert fill.preview(by_head(sample, "standup").body) == (
        "2026-11-14 standup\ndone: {{done}}\nnext: {{next}}"
    ), "the ;; typed in the box became newlines, and the date fills itself"


@pytest.mark.parametrize("text", TYPED)
def test_the_manual_shows_every_checked_query(manual, text):
    shown = f"m {text}".strip()
    assert shown in manual, f"{shown!r} is checked here, so the manual should show it"


@pytest.mark.parametrize("file", sample_files())
def test_the_manual_lists_every_sample_record(manual, file):
    line = first_line(os.path.join(EXAMPLES, file))
    assert line in manual, f"{file} should appear in the sample tree section as {line!r}"


def test_every_sample_record_was_written_by_mash_and_has_history(sample):
    touched = sample.journal.touched()
    records = [s for s in sample.tree.load().records if not s.shipped]
    assert all(len(s.identity) == ID_LENGTH for s in records), "every sample file carries an id"
    assert {s.identity for s in records} == set(touched), "and one journal line per record"
