import pytest

from mash.actions import Action, decide, perform


@pytest.mark.parametrize(
    "body, kind, target",
    [
        ("https://grafana.example.com/d/x", "open", "https://grafana.example.com/d/x"),
        ("http://127.0.0.1:4000", "open", "http://127.0.0.1:4000"),
        ("file:///Users/me/doc.pdf", "open", "file:///Users/me/doc.pdf"),
        ("ssh deploy@10.0.1.5", "copy", "ssh deploy@10.0.1.5"),
        ("me@example.com", "copy", "me@example.com"),
        ("mail me@example.com now", "copy", "mail me@example.com now"),
        ("line one\nline two", "copy", "line one\nline two"),
    ],
)
def test_decide_by_body_shape(body, kind, target):
    assert decide(body, exists=lambda p: False, flows={}) == Action(kind, target), (
        f"{body!r} should {kind} {target!r}"
    )


def test_existing_path_opens(tmp_path):
    path = str(tmp_path)
    assert decide(path, exists=lambda p: p == path, flows={}).kind == "open", (
        "a path that exists should open"
    )
    assert decide("/nope", exists=lambda p: False, flows={}).kind == "copy", (
        "a path that doesn't exist is just text"
    )


def test_tilde_path_is_expanded_before_the_check(mocker):
    exists = mocker.Mock(return_value=True)
    mocker.patch("mash.actions.os.path.expanduser", return_value="/Users/me/notes")
    action = decide("~/notes", exists=exists, flows={})
    exists.assert_called_once_with("/Users/me/notes")
    assert action.target == "/Users/me/notes", "the opened target should be the expanded path"


@pytest.mark.parametrize(
    "body, flows, target",
    [
        ("delany @kb", {}, "kb delany"),
        ("@t parser lexer", {}, "t parser lexer"),
        ("@l", {}, "l"),
        ("parser lexer @tally", {"tally": "t"}, "t parser lexer"),
        ("delany @kobold", {"kobold": "kb", "tally": "t"}, "kb delany"),
    ],
)
def test_handoff_to_another_workflow(body, flows, target):
    assert decide(body, exists=lambda p: False, flows=flows) == Action("handoff", target), (
        f"{body!r} should hand off as {target!r}"
    )


@pytest.mark.parametrize(
    "text, expected",
    [
        ("tally=t kobold=kb wisp=l", {"tally": "t", "kobold": "kb", "wisp": "l"}),
        ("", {}),
        ("  tally=t  ", {"tally": "t"}),
        ("broken", {}),
    ],
)
def test_flows_setting_parses_name_keyword_pairs(text, expected):
    from mash.actions import parse_flows

    assert parse_flows(text) == expected, f"{text!r} should give {expected}"


def test_perform_copy_uses_pbcopy(mocker):
    run = mocker.patch("subprocess.run")
    perform(Action("copy", "hello"))
    run.assert_called_once_with(["pbcopy"], input=b"hello", check=True)


def test_perform_open_uses_open(mocker):
    run = mocker.patch("subprocess.run")
    perform(Action("open", "https://x"))
    run.assert_called_once_with(["open", "https://x"], check=True)


def test_perform_handoff_drives_alfred(mocker):
    run = mocker.patch("subprocess.run")
    perform(Action("handoff", "kb delany"))
    args = run.call_args[0][0]
    assert args[0] == "osascript", "a hand-off should go through osascript"
    assert 'search "kb delany"' in args[-1], "the Alfred search should carry keyword and text"
