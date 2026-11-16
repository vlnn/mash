import os
import shutil
import time

import pytest

from mash import brain
from mash.brain import CHILD, JUMP, TAG, TAGGED, TYPE, Link
from mash.journal import Journal
from mash.tree import Tree

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES = os.path.join(REPO, "examples")

SMALL_TREE = {
    "ssh-prod-web.aaaaaa.txt": "ssh prod web -> ssh deploy@10.0.1.5",
    "next-chore.bbbbbb.txt": "next chore ~> home/chores/",
    "reading-now.cccccc.txt": "reading now => #reading",
    "home/net.dddddd.txt": "net => wifi",
    "home/wifi-guest.eeeeee.txt": "wifi guest -> hunter2",
    "home/book-dune-reading.ffffff.txt": "book dune #reading -> Herbert, 1965",
    "home/chores/water-plants.gggggg.txt": "water plants",
    "work/latest-ml-ml.hhhhhh.txt": "latest ml #ml #> paper",
    "work/paper-adam-ml.iiiiii.txt": "paper adam #ml -> https://arxiv.org/abs/1412.6980",
    "work/dashboard.jjjjjj.txt": "dashboard => wifi guest",
    "work/standup.kkkkkk.txt": "standup ->\n{{date}} standup\ndone: {{done}}",
}

SMALL_JOURNAL = [
    (1_792_400_400.0, "eeeeee", "home", "add"),
    (1_792_486_800.0, "eeeeee", "home", "copy"),
    (1_792_573_200.0, "gggggg", "home/chores", "copy"),
    (1_792_300_000.0, "dddddd", "home", "touched x4"),
]


@pytest.fixture(autouse=True)
def utc(monkeypatch):
    monkeypatch.setenv("TZ", "UTC")
    time.tzset()


def grow(root, files, journal=()):
    for name, text in files.items():
        path = os.path.join(root, *name.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    with open(os.path.join(root, ".journal.log"), "w", encoding="utf-8") as f:
        f.writelines(
            f"{stamp:.3f}\t{identity}\t{node}\t{action}\n"
            for stamp, identity, node, action in journal
        )
    return root


def plan_of(root, facts=False):
    uses = Journal(os.path.join(root, ".journal.log")).uses()
    return brain.plan(Tree(root).load(), uses, facts=facts)


@pytest.fixture
def small(tmp_path):
    return grow(str(tmp_path), SMALL_TREE, SMALL_JOURNAL)


@pytest.fixture
def skeleton(small):
    return plan_of(small)


@pytest.fixture
def full(small):
    return plan_of(small, facts=True)


@pytest.fixture(params=[False, True], ids=["skeleton", "facts"])
def examples_plan(request, tmp_path):
    root = shutil.copytree(EXAMPLES, str(tmp_path / "examples"))
    return plan_of(root, facts=request.param)


def thought(plan, key):
    return next(t for t in plan.thoughts if t.key == key)


def keys(plan):
    return {t.key for t in plan.thoughts}


@pytest.mark.parametrize(
    "key, name",
    [
        ("node:", "mash"),
        ("node:home", "home"),
        ("node:home/chores", "chores"),
        ("node:work", "work"),
    ],
)
def test_every_node_is_a_thought_named_by_its_folder(skeleton, key, name):
    assert thought(skeleton, key).name == name, f"{key} should be shown as {name!r}"
    assert thought(skeleton, key).type == "type:node", f"{key} should carry the node type"


@pytest.mark.parametrize(
    "parent, child",
    [
        ("node:", "node:home"),
        ("node:", "node:work"),
        ("node:home", "node:home/chores"),
        ("node:", "record:bbbbbb"),
        ("node:home", "record:dddddd"),
        ("node:work", "record:hhhhhh"),
    ],
)
def test_folders_and_rules_hang_under_their_node(skeleton, parent, child):
    assert Link(parent, child, CHILD) in skeleton.links, f"{child} should be a child of {parent}"


@pytest.mark.parametrize(
    "key, name, label",
    [
        ("record:bbbbbb", "next chore", "~> home/chores/"),
        ("record:cccccc", "reading now", "=> #reading"),
        ("record:dddddd", "net", "=> wifi"),
        ("record:hhhhhh", "latest ml #ml", "#> paper"),
    ],
)
def test_a_rule_is_a_thought_labelled_with_its_search(skeleton, key, name, label):
    rule = thought(skeleton, key)
    assert (rule.name, rule.label) == (name, label), f"{key} should show its head and its arrow"
    assert rule.type == "type:rule", f"{key} should carry the rule type"


@pytest.mark.parametrize(
    "key, expected",
    [
        ("record:dddddd", "net → wifi guest → hunter2"),
        ("record:bbbbbb", "next chore → water plants"),
        ("record:dddddd", "used 4 times, last on 2026-10-18"),
        ("record:cccccc", "never used"),
    ],
)
def test_a_rule_note_says_what_it_resolves_to_and_how_often(skeleton, key, expected):
    assert expected in thought(skeleton, key).note, f"{key} should explain itself with {expected!r}"


def test_a_rule_that_finds_nothing_says_so(tmp_path):
    plan = plan_of(grow(str(tmp_path), {"lost.aaaaaa.txt": "lost => nowhere"}))
    assert "nothing matches 'nowhere'" in thought(plan, "record:aaaaaa").note, (
        "a dangling rule should show why it resolves to nothing"
    )


@pytest.mark.parametrize("fact", ["record:aaaaaa", "record:eeeeee", "record:gggggg"])
def test_the_skeleton_leaves_facts_out(skeleton, fact):
    assert fact not in keys(skeleton), f"{fact} is a fact and should stay out of the skeleton"


@pytest.mark.parametrize(
    "node, line",
    [
        ("node:", "- **ssh prod web** → `ssh deploy@10.0.1.5`"),
        ("node:", "- **next chore** `~> home/chores/`"),
        ("node:home/chores", "- **water plants**"),
        ("node:work", "- **standup** → `{{date}} standup` …"),
    ],
)
def test_a_skeleton_node_lists_its_own_records_in_its_note(skeleton, node, line):
    assert line in thought(skeleton, node).note.split("\n"), f"{node} should list {line!r}"


def test_a_node_note_is_sorted_by_head(skeleton):
    heads = [line.split("**")[1] for line in thought(skeleton, "node:home").note.split("\n")]
    assert heads == ["book dune #reading", "net", "wifi guest"], "records should be listed A to Z"


@pytest.mark.parametrize(
    "node, label",
    [
        ("node:", "11 records · last used 2026-10-21"),
        ("node:home", "4 records · last used 2026-10-21"),
        ("node:home/chores", "1 record · last used 2026-10-21"),
        ("node:work", "4 records"),
    ],
)
def test_a_node_label_counts_its_subtree_and_dates_its_last_use(skeleton, node, label):
    assert thought(skeleton, node).label == label, f"{node} should be labelled {label!r}"


@pytest.mark.parametrize("tag", ["tag:#reading", "tag:#ml"])
def test_every_tag_is_a_tag_thought(skeleton, tag):
    assert thought(skeleton, tag).kind == TAG, f"{tag} should be a TheBrain tag"
    assert thought(skeleton, tag).name == tag[len("tag:") :], f"{tag} should keep its # spelling"


@pytest.mark.parametrize(
    "tagged, tag, why",
    [
        ("node:home", "tag:#reading", "a skeleton node carries the tags of its own facts"),
        ("node:work", "tag:#ml", "a skeleton node carries the tags of its own facts"),
        ("record:hhhhhh", "tag:#ml", "a rule carries the tags in its head"),
        ("record:cccccc", "tag:#reading", "a rule carries the tags it searches for"),
    ],
)
def test_tags_are_attached(skeleton, tagged, tag, why):
    assert Link(tagged, tag, TAGGED) in skeleton.links, why


def test_a_node_is_not_tagged_through_its_subfolders(skeleton):
    assert Link("node:", "tag:#reading", TAGGED) not in skeleton.links, (
        "only a node's own records tag it, or every tag would end up on the root"
    )


@pytest.mark.parametrize(
    "rule, target, arrow, why",
    [
        ("record:bbbbbb", "node:home/chores", "~>", "a rule naming a node points at that node"),
        ("record:jjjjjj", "node:home", "=>", "a rule points at the node its best hit lives in"),
    ],
)
def test_a_skeleton_rule_jumps_to_where_its_search_lands(skeleton, rule, target, arrow, why):
    assert Link(rule, target, JUMP, arrow) in skeleton.links, why


def test_a_rule_resolving_inside_its_own_node_needs_no_jump(skeleton):
    jumps = [
        link for link in skeleton.links if link.source == "record:dddddd" and link.relation == JUMP
    ]
    assert jumps == [], "home/net finds home/wifi guest, and home is already its parent"


@pytest.mark.parametrize(
    "key, name, label, url",
    [
        ("record:aaaaaa", "ssh prod web", "ssh deploy@10.0.1.5", ""),
        ("record:gggggg", "water plants", "", ""),
        (
            "record:iiiiii",
            "paper adam #ml",
            "https://arxiv.org/abs/1412.6980",
            "https://arxiv.org/abs/1412.6980",
        ),
        ("record:kkkkkk", "standup", "{{date}} standup …", ""),
    ],
)
def test_with_facts_every_fact_is_a_thought(full, key, name, label, url):
    fact = thought(full, key)
    assert (fact.name, fact.label, fact.url) == (name, label, url), (
        f"{key} should show its head, the first line of its body, and a link when it is one"
    )
    assert fact.type == "type:fact", f"{key} should carry the fact type"


def test_a_fact_note_holds_the_body_verbatim(full):
    assert thought(full, "record:kkkkkk").note == "```\n{{date}} standup\ndone: {{done}}\n```", (
        "the body should be fenced so TheBrain does not reflow it"
    )


def test_a_fence_outgrows_the_backticks_in_a_body(tmp_path):
    plan = plan_of(grow(str(tmp_path), {"md.aaaaaa.txt": "md ->\n```\ncode\n```"}), facts=True)
    assert thought(plan, "record:aaaaaa").note.startswith("````\n"), (
        "a body with a ``` fence should be wrapped in a longer one"
    )


@pytest.mark.parametrize(
    "link, why",
    [
        (Link("record:dddddd", "record:eeeeee", JUMP, "=>"), "a rule jumps to the fact it finds"),
        (Link("record:ffffff", "tag:#reading", TAGGED), "a fact carries its own tags"),
        (Link("node:home", "record:eeeeee", CHILD), "a fact hangs under its node"),
    ],
)
def test_with_facts_links_reach_the_facts(full, link, why):
    assert link in full.links, why


def test_with_facts_nodes_leave_tags_and_listings_to_their_facts(full):
    assert Link("node:home", "tag:#reading", TAGGED) not in full.links, "the fact is tagged instead"
    assert thought(full, "node:home").note == "", "the facts are visible as children instead"


@pytest.mark.parametrize(
    "facts, types",
    [
        (False, {"type:node", "type:rule"}),
        (True, {"type:node", "type:rule", "type:fact"}),
    ],
)
def test_types_exist_only_when_something_uses_them(small, facts, types):
    plan = plan_of(small, facts=facts)
    assert {t.key for t in plan.thoughts if t.kind == TYPE} == types, f"facts={facts} needs {types}"


def test_a_handmade_record_is_keyed_by_its_place(tmp_path):
    plan = plan_of(grow(str(tmp_path), {"work/notes.txt": "notes => work"}))
    assert "record:work/notes" in keys(plan), "a file without an id is identified by its place"


def test_every_link_joins_two_planned_thoughts(examples_plan):
    known = keys(examples_plan)
    loose = [link for link in examples_plan.links if not {link.source, link.target} <= known]
    assert loose == [], "a link to a thought that is not in the plan cannot be pushed"


def test_no_two_thoughts_are_linked_twice(examples_plan):
    pairs = [frozenset((link.source, link.target)) for link in examples_plan.links]
    assert len(pairs) == len(set(pairs)), "TheBrain keeps one link per pair, a second rewrites it"


def test_no_thought_is_linked_to_itself(examples_plan):
    loops = [link for link in examples_plan.links if link.source == link.target]
    assert loops == [], "TheBrain refuses a link from a thought to itself"


def test_thought_keys_are_unique(examples_plan):
    listed = [t.key for t in examples_plan.thoughts]
    assert len(listed) == len(set(listed)), "the key is what the sync remembers a thought by"


def test_everything_but_the_root_has_one_parent(examples_plan):
    children = [link.target for link in examples_plan.links if link.relation == CHILD]
    ordinary = [t.key for t in examples_plan.thoughts if t.kind not in (TYPE, TAG)]
    assert sorted(children) == sorted(k for k in ordinary if k != "node:"), (
        "each node, rule and fact should hang under exactly one node"
    )


@pytest.mark.parametrize(
    "link, why",
    [
        (
            Link("record:xkdrvh", "node:home/chores", JUMP, "~>"),
            "next chore is a queue over chores",
        ),
        (Link("record:25w7o1", "tag:#reading", TAGGED), "reading now is a view of #reading"),
        (Link("node:home", "tag:#reading", TAGGED), "home holds a #reading book"),
        (Link("node:work", "tag:#reading", TAGGED), "work holds a #reading paper"),
        (Link("record:pn6y85", "node:work", JUMP, "=>"), "dashboard finds grafana in work"),
    ],
)
def test_the_sample_tree_shows_its_wiring(tmp_path, link, why):
    root = shutil.copytree(EXAMPLES, str(tmp_path / "examples"))
    assert link in plan_of(root).links, why


def test_planning_twice_gives_the_same_plan(small):
    assert plan_of(small) == plan_of(small), "an unchanged tree should sync as no change"


@pytest.mark.parametrize(
    "line",
    [
        "mash  ·  11 records · last used 2026-10-21",
        "  home  ·  4 records · last used 2026-10-21  #reading",
        "    chores  ·  1 record · last used 2026-10-21",
        "    net  ·  => wifi",
        "  next chore  ·  ~> home/chores/  ⇢ chores",
        "  reading now  ·  => #reading  #reading",
    ],
)
def test_the_outline_shows_the_plan_as_an_indented_tree(skeleton, line):
    assert line in brain.outline(skeleton), f"the outline should have the line {line!r}"
