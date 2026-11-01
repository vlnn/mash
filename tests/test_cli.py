import json

import pytest

from mash import cli


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("MASH_FOLDER", str(tmp_path / "mash"))
    cli.main(["add", "ssh prod web -> ssh deploy@10.0.1.5"])
    cli.main(["add", "body/ weight kg #body -> 80"])
    cli.main(["add", "body/ weight ~> weight kg"])
    return tmp_path / "mash"


def test_best_prints_resolved_body(home, capsys):
    assert cli.main(["weight"]) == 0, "a hit exits 0"
    assert capsys.readouterr().out == "80\n", "a rule is resolved before printing"


def test_best_fills_date_in_the_printed_body(home, capsys, mocker):
    mocker.patch("mash.fill.today", return_value="2026-11-01")
    cli.main(["add", "stamp -> {{date}} note {{other}}"])
    capsys.readouterr()
    cli.main(["stamp"])
    assert capsys.readouterr().out == "2026-11-01 note {{other}}\n", "date fills, other blanks stay"


def test_miss_exits_one(home, capsys):
    assert cli.main(["zzz"]) == 1, "no hit exits 1"
    assert capsys.readouterr().out == "", "and prints nothing"


def test_listing(home, capsys):
    cli.main(["-l", "weight"])
    lines = capsys.readouterr().out.splitlines()
    assert [line.split("  ·  ")[0].split()[-1] for line in lines] == ["weight", "#body"], (
        "the list shows both weight records, tighter head first"
    )


def test_add_reports_node_and_head(home, capsys):
    cli.main(["add", "work/ k8 ctx -> kubectl"])
    assert capsys.readouterr().out == "Added to work/: k8 ctx\n"
    (path,) = (home / "work").glob("k8-ctx.*.txt")
    assert path.read_text() == "k8 ctx -> kubectl\n"


def test_fill(home, capsys, mocker):
    mocker.patch("mash.alfred.read_clipboard", return_value="")
    cli.main(["fill", "ssh {{user=root}}@{{host}}", "host=db"])
    assert capsys.readouterr().out == "ssh root@db\n"


def test_forget_asks_then_deletes(home, capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("y\n"))
    assert cli.main(["forget", "prod"]) == 0
    assert "Deleted: ssh prod web" in capsys.readouterr().out
    assert not list(home.glob("ssh-prod-web.*")), "the file is gone"


def test_forget_declined_keeps_file(home, monkeypatch):
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("n\n"))
    assert cli.main(["forget", "prod"]) == 1
    assert list(home.glob("ssh-prod-web.*")), "n keeps the file"


def test_forget_node(home, capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("y\n"))
    assert cli.main(["forget", "--node", "body/"]) == 0
    assert not (home / "body").exists(), "the node folder is gone"


def test_alfred_json(home, capsys):
    cli.main(["--alfred", "prod"])
    items = json.loads(capsys.readouterr().out)["items"]
    assert [i["title"] for i in items] == ["ssh prod web", "Add: prod"]


def test_act_round_trip(home, capsys, mocker):
    mocker.patch("mash.alfred.actions.perform")
    cli.main(["--alfred", "prod"])
    row = json.loads(capsys.readouterr().out)["items"][0]
    cli.main(["--act", row["arg"]])
    assert capsys.readouterr().out == "Copied: ssh deploy@10.0.1.5\n"


def test_no_arguments_lists_everything(home, capsys):
    assert cli.main([]) == 0
    assert len(capsys.readouterr().out.splitlines()) == 3


def test_settings_come_from_alfred_variables(monkeypatch):
    monkeypatch.setenv("flows", "tally=t kobold=kb")
    monkeypatch.setenv("max_results", "7")
    monkeypatch.setenv("editor", "code {file}")
    assert cli.settings() == cli.alfred.Settings(
        editor="code {file}", flows={"tally": "t", "kobold": "kb"}, max_results=7
    )
