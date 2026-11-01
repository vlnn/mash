import pytest

from mash.query import parse as query
from mash.records import from_box
from mash.search import search
from mash.tree import Stored


def stored(line, node="", mtime=0.0):
    return Stored(from_box(line), node, f"/{node}/{line}.txt", mtime)


CORPUS = [
    stored("ssh prod web -> ssh deploy@10.0.1.5", mtime=3),
    stored("ssh staging web -> ssh deploy@10.0.2.5", mtime=2),
    stored("k8s ctx prod kube -> kubectl config use-context prod", node="work", mtime=5),
    stored("k8s ctx staging kube -> kubectl config use-context staging", node="work/k8s", mtime=4),
    stored("grafana latency -> https://grafana.example.com", mtime=1),
    stored("weight kg #body -> 80", node="body", mtime=6),
    stored("weight kg #body -> 79", node="body", mtime=7),
]


def heads(hits):
    return [hit.stored.record.head for hit in hits]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("prod", ["ssh prod web", "k8s ctx prod kube"]),
        ("web ssh", ["ssh prod web", "ssh staging web"]),
        ("stg", ["ssh staging web", "k8s ctx staging kube"]),
        ("k8 prd", ["k8s ctx prod kube"]),
        ("grf lat", ["grafana latency"]),
        ("deploy", ["ssh prod web", "ssh staging web"]),
        ("ssh prod staging", []),
    ],
)
def test_ranking_by_relevance(text, expected):
    assert heads(search(CORPUS, query(text))) == expected, f"{text!r} should rank {expected}"


def test_empty_query_lists_everything_newest_first():
    assert heads(search(CORPUS, query(""))) == [
        "weight kg #body",
        "weight kg #body",
        "k8s ctx prod kube",
        "k8s ctx staging kube",
        "ssh prod web",
        "ssh staging web",
        "grafana latency",
    ], "an empty query should browse all records, most recently touched first"


def test_equal_scores_go_to_fewer_head_words_then_newest():
    hits = search(CORPUS, query("web"))
    assert heads(hits) == ["ssh prod web", "ssh staging web"], (
        "same score and length should fall to the newer record"
    )


def test_newest_breaks_ties_by_default_and_oldest_with_tilde():
    newest = search(CORPUS, query("weight kg"))
    oldest = search(CORPUS, query("~> weight kg"))
    assert newest[0].stored.record.body == "79", "default order should put the newest first"
    assert oldest[0].stored.record.body == "80", "~> should put the oldest first"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("work/", ["k8s ctx prod kube", "k8s ctx staging kube"]),
        ("work/ ctx", ["k8s ctx prod kube", "k8s ctx staging kube"]),
        ("work/k8s/ ctx", ["k8s ctx staging kube"]),
        ("body/", ["weight kg #body", "weight kg #body"]),
        ("work/ weight", []),
    ],
)
def test_naming_a_node_narrows_to_its_subtree(text, expected):
    assert heads(search(CORPUS, query(text))) == expected, f"{text!r} should see {expected}"


def test_touch_times_override_mtime():
    touched = {("", "grafana latency"): 100.0}
    hits = search(CORPUS, query(""), touched)
    assert heads(hits)[0] == "grafana latency", "a journal touch should outrank file mtime"


def test_hits_carry_scores():
    hit = search(CORPUS, query("prod"))[0]
    assert hit.score == 8, "a whole-word hit should carry its score"
