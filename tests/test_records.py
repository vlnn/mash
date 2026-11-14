import pytest

from mash.records import from_box, parse, render, slug


@pytest.mark.parametrize(
    "text, head, arrow, body",
    [
        ("ssh prod web -> ssh deploy@10.0.1.5", "ssh prod web", "->", "ssh deploy@10.0.1.5"),
        (
            "find py rm -> find . -name '*.pyc' -exec rm {} \\;",
            "find py rm",
            "->",
            "find . -name '*.pyc' -exec rm {} \\;",
        ),
        (
            "logs api -> tail -f app.log | grep ERROR",
            "logs api",
            "->",
            "tail -f app.log | grep ERROR",
        ),
        ("c pointer -> int *p = &x;  // x -> p", "c pointer", "->", "int *p = &x;  // x -> p"),
        ("bins go out on thursday", "bins go out on thursday", "->", "bins go out on thursday"),
        ("ssh prod web   ->   ssh x", "ssh prod web", "->", "ssh x"),
        ("кава coffee -> order", "кава coffee", "->", "order"),
    ],
)
def test_facts(text, head, arrow, body):
    record = parse(text)
    assert record.head == head, f"{text!r} should have head {head!r}"
    assert record.arrow == arrow, f"{text!r} should have arrow {arrow!r}"
    assert record.body == body, f"{text!r} should have body {body!r}"
    assert not record.is_rule, f"{text!r} should be a fact"


@pytest.mark.parametrize(
    "text, head, arrow, query",
    [
        ("weight ~> weight kg", "weight", "~>", "weight kg"),
        ("k8 => kubernetes kube", "k8", "=>", "kubernetes kube"),
        ("reading now => #reading", "reading now", "=>", "#reading"),
        ("latest ~/> weight kg", "latest", "~/>", "weight kg"),
        ("same /#> ctx", "same", "/#>", "ctx"),
        ("prod box => infra/ ssh prod", "prod box", "=>", "infra/ ssh prod"),
    ],
)
def test_rules(text, head, arrow, query):
    record = parse(text)
    assert record.head == head, f"{text!r} should have head {head!r}"
    assert record.arrow == arrow, f"{text!r} should have arrow {arrow!r}"
    assert record.query == query, f"{text!r} should have query {query!r}"
    assert record.is_rule, f"{text!r} should be a rule"
    assert record.body == "", "a rule should have no body of its own"


@pytest.mark.parametrize(
    "text, body",
    [
        ("release notes ->\n## {{version}}\n- {{done}}\n", "## {{version}}\n- {{done}}"),
        (
            "standup ->\n    {{date}} standup\n    done: {{done}}\n",
            "    {{date}} standup\n    done: {{done}}",
        ),
        ("a -> first\nsecond\n\nfourth\n", "first\nsecond\n\nfourth"),
        ("a ->", ""),
        ("a ->\n", ""),
        ("plain\nmore\n", "plain\nmore"),
    ],
)
def test_multiline_bodies(text, body):
    assert parse(text).body == body, f"{text!r} should have body {body!r}"


@pytest.mark.parametrize(
    "text, words, tags",
    [
        ("weight kg #body -> 80", ("weight", "kg", "#body"), ("#body",)),
        (
            "paper attention #reading #ml -> x",
            ("paper", "attention", "#reading", "#ml"),
            ("#reading", "#ml"),
        ),
        ("a,b, c -> x", ("a", "b", "c"), ()),
        ("kube: ctx -> x", ("kube:", "ctx"), ()),
    ],
)
def test_head_words_and_tags(text, words, tags):
    record = parse(text)
    assert record.words == words, f"{text!r} should split into {words}"
    assert record.tags == tags, f"{text!r} should carry tags {tags}"


@pytest.mark.parametrize(
    "line, body",
    [
        ("release notes -> ## {{version}};;- {{done}}", "## {{version}}\n- {{done}}"),
        (
            "standup -> {{date}};;done: {{done}};;next: {{next}}",
            "{{date}}\ndone: {{done}}\nnext: {{next}}",
        ),
        ("find py -> find . -exec rm {} \\;", "find . -exec rm {} \\;"),
        ("two -> a; b", "a; b"),
        ("case arm -> x) echo \\;;", "x) echo ;;"),
    ],
)
def test_from_box_expands_double_semicolon(line, body):
    assert from_box(line).body == body, f"{line!r} typed in the box should have body {body!r}"


@pytest.mark.parametrize(
    "line",
    [
        "ssh prod web -> ssh deploy@10.0.1.5",
        "weight ~> weight kg",
        "bins go out on thursday",
        "release notes -> ## {{version}};;- {{done}}",
    ],
)
def test_render_round_trips_through_parse(line):
    record = from_box(line)
    assert parse(render(record)) == record, f"{line!r} should survive render then parse"


@pytest.mark.parametrize(
    "line, text",
    [
        ("ssh prod web -> ssh deploy@10.0.1.5", "ssh prod web -> ssh deploy@10.0.1.5\n"),
        ("standup -> {{date}};;done: {{done}}", "standup -> {{date}}\ndone: {{done}}\n"),
        ("weight ~> weight kg", "weight ~> weight kg\n"),
        ("bins go out on thursday", "bins go out on thursday\n"),
    ],
)
def test_render_file_text(line, text):
    assert render(from_box(line)) == text, f"{line!r} should be stored as {text!r}"


@pytest.mark.parametrize(
    "head, name",
    [
        ("ssh prod web", "ssh-prod-web"),
        ("weight kg #body", "weight-kg-body"),
        ("http://127.0.0.1:4000", "http-127-0-0-1-4000"),
        ("Snow Crash, 1992", "snow-crash-1992"),
        ("кава coffee", "кава-coffee"),
        ("---", "record"),
        ("", "record"),
    ],
)
def test_slug(head, name):
    assert slug(head) == name, f"{head!r} should be filed as {name!r}"
