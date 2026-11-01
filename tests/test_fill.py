import pytest

from mash.fill import blanks, fill, preview


@pytest.mark.parametrize(
    "body, expected",
    [
        (
            "ssh {{user=root}}@{{host}} -p {{port=22}}",
            [("user", "root"), ("host", None), ("port", "22")],
        ),
        ("https://x/browse/{{ticket}}", [("ticket", None)]),
        ("{{date}} standup: {{done}} / {{next}}", [("done", None), ("next", None)]),
        ("`{{clipboard}}`", []),
        ("{{a}} and {{a}} again", [("a", None)]),
        ('{} ${VAR} {"a": 1} {{ not a name }}', []),
        ("{{with-dash_1}}", [("with-dash_1", None)]),
        ("plain", []),
    ],
)
def test_blanks_in_order_of_first_appearance(body, expected):
    assert blanks(body) == expected, f"{body!r} should ask for {expected}"


@pytest.mark.parametrize(
    "body, values, expected",
    [
        ("ssh {{user=root}}@{{host}}", {"host": "db"}, "ssh root@db"),
        ("ssh {{user=root}}@{{host}}", {"host": "db", "user": "deploy"}, "ssh deploy@db"),
        ("{{a}} {{a}}", {"a": "x"}, "x x"),
        ("no blanks", {}, "no blanks"),
    ],
)
def test_fill_uses_values_then_defaults(body, values, expected):
    assert fill(body, values, clipboard=lambda: "") == expected, (
        f"{body!r} with {values} should give {expected!r}"
    )


def test_fill_resolves_reserved_names(mocker):
    mocker.patch("mash.fill.today", return_value="2026-11-01")
    mocker.patch("mash.fill.clock", return_value="14:05")
    out = fill("{{date}} {{time}} `{{clipboard}}`", {}, clipboard=lambda: "pasted")
    assert out == "2026-11-01 14:05 `pasted`", "date, time and clipboard should fill themselves"


def test_fill_leaves_unknown_blanks_untouched():
    assert fill("{{host}}", {}, clipboard=lambda: "") == "{{host}}", (
        "a missing value keeps the blank"
    )


def test_preview_fills_date_and_time_but_never_reads_the_clipboard(mocker):
    mocker.patch("mash.fill.today", return_value="2026-11-01")
    mocker.patch("mash.fill.clock", return_value="14:05")
    clipboard = mocker.Mock()
    out = preview("{{date}} {{time}} {{clipboard}} {{host}}")
    assert out == "2026-11-01 14:05 {{clipboard}} {{host}}", "preview resolves only date and time"
    clipboard.assert_not_called()
