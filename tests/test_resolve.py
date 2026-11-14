import pytest

from mash.records import from_box
from mash.resolve import DEPTH_CAP, resolve
from mash.tree import Stored


def stored(line, node="", mtime=0.0):
    return Stored(from_box(line), node, f"/{node}/{line}.txt", mtime)


def by_head(corpus, head, node=None):
    return next(s for s in corpus if s.record.head == head and (node is None or s.node == node))


CORPUS = [
    stored("weight kg #body -> 80", node="body", mtime=1),
    stored("weight kg #body -> 79", node="body", mtime=2),
    stored("weight ~> weight kg", node="body"),
    stored("weight now => weight kg", node="body"),
    stored("k8 => kubernetes kube"),
    stored("kubernetes kube ctx staging -> kubectl config use-context staging", node="work"),
    stored("kubectl => k8", node="work"),
    stored("loop a => loop b"),
    stored("loop b => loop a"),
    stored("nothing => zzz"),
    stored("ctx -> outer ctx", mtime=5),
    stored("ctx -> inner ctx", node="work", mtime=1),
    stored("here /> outer", node="work"),
    stored("anywhere => ctx", node="work"),
    stored("elsewhere => body/ weight kg"),
    stored("tagged #ml -> ml thing", node="papers", mtime=1),
    stored("tagged #other -> other thing", node="papers", mtime=9),
    stored("best tagged #ml #> tagged", node="papers"),
]


@pytest.mark.parametrize(
    "head, body",
    [
        ("weight", "80"),
        ("weight now", "79"),
        ("k8", "kubectl config use-context staging"),
        ("kubectl", "kubectl config use-context staging"),
    ],
)
def test_rules_resolve_to_a_fact(head, body):
    result = resolve(CORPUS, by_head(CORPUS, head))
    assert result.fact.record.body == body, f"{head!r} should resolve to {body!r}"


def test_chain_lists_every_step():
    result = resolve(CORPUS, by_head(CORPUS, "kubectl"))
    assert [s.record.head for s in result.chain] == [
        "kubectl",
        "k8",
        "kubernetes kube ctx staging",
    ], "the chain should show each rule followed, ending at the fact"


def test_context_is_the_rules_own_subtree_first():
    result = resolve(CORPUS, by_head(CORPUS, "anywhere"))
    assert result.fact.record.body == "inner ctx", "the rule's own subtree should win over the tree"


def test_context_falls_back_to_the_whole_tree():
    result = resolve(CORPUS, by_head(CORPUS, "elsewhere"))
    assert result.fact.record.body == "79", "a node/ in the query should look there"


def test_rule_with_nothing_in_its_subtree_searches_the_tree():
    corpus = CORPUS + [stored("far => outer", node="lonely")]
    result = resolve(corpus, by_head(corpus, "far"))
    assert result.fact.record.body == "outer ctx", "an empty subtree should fall back to the tree"


def test_subtree_axis_pins_the_context():
    result = resolve(CORPUS, by_head(CORPUS, "here"))
    assert result.fact is None, "/> should never leave the rule's subtree"


def test_same_tags_axis_filters_by_the_rules_tags():
    result = resolve(CORPUS, by_head(CORPUS, "best tagged #ml"))
    assert result.fact.record.body == "ml thing", "#> should keep only records sharing a tag"


def test_loop_stops_at_the_depth_cap():
    result = resolve(CORPUS, by_head(CORPUS, "loop a"))
    assert result.fact is None, "a loop should not produce a fact"
    assert len(result.chain) == DEPTH_CAP, "the chain should stop at the cap"
    assert "depth" in result.error, "the error should say why it stopped"


def test_no_hit_reports_an_error():
    result = resolve(CORPUS, by_head(CORPUS, "nothing"))
    assert result.fact is None, "a query with no hits resolves to nothing"
    assert "zzz" in result.error, "the error should name the query that found nothing"


def test_resolving_a_fact_is_the_fact_itself():
    fact = by_head(CORPUS, "ctx", node="")
    result = resolve(CORPUS, fact)
    assert result.fact is fact, "a fact resolves to itself"
    assert result.chain == [fact], "with a one-step chain"


def test_a_rule_read_afresh_is_not_its_own_hit():
    corpus = [stored("latest paper => paper"), stored("paper sizes and weights -> A4")]
    read_again = corpus[0]._replace()
    chain = resolve(corpus, read_again).chain
    assert [s.record.head for s in chain] == ["latest paper", "paper sizes and weights"], (
        "a rule whose query matches its own head still resolves past itself"
    )
