import pytest

from mash.query import parse


@pytest.mark.parametrize(
    "text, words",
    [
        ("prod", ("prod",)),
        ("web ssh", ("web", "ssh")),
        ("  k8   prd ", ("k8", "prd")),
        ("", ()),
        ("кав", ("кав",)),
    ],
)
def test_plain_words(text, words):
    assert parse(text).words == words, f"{text!r} should give words {words}"


@pytest.mark.parametrize(
    "text, tags, words",
    [
        ("#reading", ("#reading",), ()),
        ("#reading snow", ("#reading",), ("snow",)),
        ("#ml #reading", ("#ml", "#reading"), ()),
        ("snow #re crash", ("#re",), ("snow", "crash")),
    ],
)
def test_tags_are_separate_from_words(text, tags, words):
    query = parse(text)
    assert query.tags == tags, f"{text!r} should filter by tags {tags}"
    assert query.words == words, f"{text!r} should search words {words}"


@pytest.mark.parametrize(
    "text, node, words",
    [
        ("work/", "work", ()),
        ("work/ ctx", "work", ("ctx",)),
        ("work/k8s/ ctx", "work/k8s", ("ctx",)),
        ("ctx work/", "work", ("ctx",)),
        ("prod", "", ("prod",)),
        ("wo", "", ("wo",)),
    ],
)
def test_node_term(text, node, words):
    query = parse(text)
    assert query.node == node, f"{text!r} should name node {node!r}"
    assert query.words == words, f"{text!r} should search words {words}"


@pytest.mark.parametrize(
    "text, axes, words",
    [
        ("~> weight kg", "~", ("weight", "kg")),
        ("~>", "~", ()),
        ("=> weight", "", ("weight",)),
        ("=~> weight", "~", ("weight",)),
        ("~/> weight", "~/", ("weight",)),
        ("/#> ctx", "/#", ("ctx",)),
        ("weight", "", ("weight",)),
    ],
)
def test_leading_arrow_sets_axes(text, axes, words):
    query = parse(text)
    assert query.axes == axes, f"{text!r} should set axes {axes!r}"
    assert query.words == words, f"{text!r} should search words {words}"
    assert query.add is None, f"{text!r} is a search, not an add"


def test_arrow_after_node_still_sets_axes():
    query = parse("work/ /> ctx")
    assert query.node == "work", "node should be read before the arrow"
    assert query.axes == "/", "arrow after the node should set axes"
    assert query.words == ("ctx",), "words after the arrow are the query"


@pytest.mark.parametrize(
    "text, head, arrow, node",
    [
        ("ssh prod web -> ssh deploy@10.0.1.5", "ssh prod web", "->", ""),
        ("weight ~> weight kg", "weight", "~>", ""),
        ("work/ k8 ctx -> kubectl config use-context staging", "k8 ctx", "->", "work"),
        ("work/k8s/ ctx staging -> x", "ctx staging", "->", "work/k8s"),
        ("standup -> {{date}};;done: {{done}}", "standup", "->", ""),
    ],
)
def test_arrow_with_head_is_an_add(text, head, arrow, node):
    query = parse(text)
    assert query.add is not None, f"{text!r} should offer an add"
    assert query.add.head == head, f"{text!r} should add a record headed {head!r}"
    assert query.add.arrow == arrow, f"{text!r} should add with arrow {arrow!r}"
    assert query.node == node, f"{text!r} should add into node {node!r}"


def test_add_still_searches_its_head_words():
    query = parse("ssh prod web #infra -> ssh deploy@10.0.1.5")
    assert query.words == ("ssh", "prod", "web"), "head words should be searched while adding"
    assert query.tags == ("#infra",), "head tags should filter while adding"
    assert query.axes == "", "an add has no axes of its own"


@pytest.mark.parametrize(
    "text, node, body",
    [
        ("site -> https://example.com/", "", "https://example.com/"),
        ("notes -> ~/notes/", "", "~/notes/"),
        ("work/ site -> https://example.com/", "work", "https://example.com/"),
    ],
)
def test_node_is_only_read_before_the_arrow(text, node, body):
    query = parse(text)
    assert query.node == node, f"{text!r} should add into node {node!r}"
    assert query.add.body == body, f"{text!r} should keep its body {body!r}"


def test_add_body_expands_box_newlines():
    query = parse("standup -> {{date}};;done: {{done}}")
    assert query.add.body == "{{date}}\ndone: {{done}}", (
        ";; typed in the box should become a newline"
    )
