import pytest

from mash.match import score, score_head_word, score_tag
from mash.query import parse as query
from mash.records import from_box as record


@pytest.mark.parametrize(
    "term, word, expected",
    [
        ("prod", "prod", 8),
        ("PROD", "prod", 8),
        ("pro", "prod", 6),
        ("rod", "prod", 4),
        ("prd", "prod", 2),
        ("stg", "staging", 2),
        ("stgng", "staging", 2),
        ("stgaing", "staging", 0),
        ("k8", "k8s", 6),
        ("4000", "http://127.0.0.1:4000", 4),
        ("кав", "кава", 6),
        ("kube", "kube:", 6),
        ("x", "prod", 0),
    ],
)
def test_head_word_tiers(term, word, expected):
    assert score_head_word(term, word) == expected, (
        f"{term!r} against {word!r} should score {expected}"
    )


@pytest.mark.parametrize(
    "term, tag, expected",
    [
        ("#re", "#reading", 6),
        ("#re", "#read", 6),
        ("#read", "#read", 8),
        ("#read", "#reading", 6),
        ("#reading", "#read", 0),
        ("#reading", "#reading", 8),
        ("#ml", "#reading", 0),
    ],
)
def test_tag_prefix_rule(term, tag, expected):
    assert score_tag(term, tag) == expected, f"{term!r} against {tag!r} should score {expected}"


@pytest.mark.parametrize(
    "text, line, expected",
    [
        ("prod", "ssh prod web -> ssh deploy@10.0.1.5", 8),
        ("web ssh", "ssh prod web -> ssh deploy@10.0.1.5", 16),
        ("k8 prd", "k8s ctx prod kube -> x", 8),
        ("grf lat", "grafana latency -> x", 8),
        ("deploy", "ssh prod web -> ssh deploy@10.0.1.5", 1),
        ("dply", "ssh prod web -> ssh deploy@10.0.1.5", 1),
        ("use-context", "k8s ctx -> kubectl config use-context staging", 1),
        ("ssh prod staging", "ssh prod web -> ssh deploy@10.0.1.5", 0),
        ("kctx", "k8s ctx -> x", 0),
        ("k ctx", "k8s ctx -> x", 14),
        ("", "anything -> x", 0),
        ("prod", "pihole prod finished", 8),
    ],
)
def test_record_score(text, line, expected):
    assert score(query(text), record(line)) == expected, (
        f"{text!r} against {line!r} should score {expected}"
    )


@pytest.mark.parametrize(
    "text, line, expected",
    [
        ("#reading", "book snow crash #reading -> x", 8),
        ("#re", "book snow crash #reading -> x", 6),
        ("#reading snow", "book snow crash #reading -> x", 16),
        ("#ml #reading", "paper attention #reading #ml -> x", 16),
        ("#ml #reading", "book snow crash #reading -> x", 0),
        ("#reading", "book snow crash #read -> x", 0),
        ("snow", "book snow crash #reading -> x", 8),
    ],
)
def test_tag_filter_in_query(text, line, expected):
    assert score(query(text), record(line)) == expected, (
        f"{text!r} against {line!r} should score {expected}"
    )


def test_head_match_beats_any_body_match():
    through_head = score(query("deploy"), record("deploy script -> run it"))
    through_body = score(
        query("deploy"), record("ssh prod web -> ssh deploy@10.0.1.5 and deploy again")
    )
    assert through_head > through_body, "a head hit should always outrank a body hit"


def test_plain_word_matches_a_tag_by_prefix_only():
    assert score(query("read"), record("book #reading -> x")) == 6, (
        "a plain word should prefix-match a tag"
    )
    assert score(query("reading"), record("book #read -> x")) == 0, (
        "a tag never matches a longer term"
    )
