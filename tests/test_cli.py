import json
import time

import pytest

from mash import cli


def seed(tmp_path, monkeypatch):
    monkeypatch.setenv("MASH_FOLDER", str(tmp_path / "mash"))
    cli.main(["add", "ssh prod web -> ssh deploy@10.0.1.5"])
    cli.main(["add", "body/ weight kg #body -> 80"])
    cli.main(["add", "body/ weight ~> weight kg"])
    return tmp_path / "mash"


@pytest.fixture
def home(tmp_path, monkeypatch):
    return seed(tmp_path, monkeypatch)


@pytest.fixture
def home_on_the_first_of_november(tmp_path, monkeypatch, mocker):
    monkeypatch.setenv("TZ", "UTC")
    time.tzset()
    mocker.patch("mash.journal.now", return_value=1_793_500_000.0)
    return seed(tmp_path, monkeypatch)


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
    mocker.patch("mash.session.read_clipboard", return_value="")
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
    mocker.patch("mash.session.actions.perform")
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
    assert cli.settings() == cli.Settings(
        editor="code {file}", flows={"tally": "t", "kobold": "kb"}, max_results=7
    )


def test_adding_the_same_record_again_says_it_is_already_there(home, capsys):
    capsys.readouterr()
    cli.main(["add", "ssh prod web -> ssh deploy@10.0.1.5"])
    assert capsys.readouterr().out == "Already there: ssh prod web\n", (
        "no second file, and it says so"
    )
    assert len(list(home.glob("ssh-prod-web.*.txt"))) == 1, "one file for one record"


@pytest.fixture
def manual(tmp_path, monkeypatch):
    from mash.records import from_box
    from mash.tree import Tree

    tree = Tree(str(tmp_path / "manual"))
    tree.add("keys", from_box("shift enter key -> pastes"))
    monkeypatch.setattr(cli, "MANUAL", tree.root)
    return tmp_path / "manual"


def test_the_manual_is_searched_when_help_is_named(home, manual, capsys):
    capsys.readouterr()
    assert cli.main(["help/", "shift"]) == 0, "help/ makes the shipped record a hit"
    assert capsys.readouterr().out == "pastes\n", "and its body is printed like any other"


@pytest.mark.parametrize("argv", [["shift"], ["-l", "shift"], ["-l"]])
def test_the_manual_stays_out_of_ordinary_commands(home, manual, capsys, argv):
    capsys.readouterr()
    cli.main(argv)
    assert "pastes" not in capsys.readouterr().out, f"mash {' '.join(argv)} is about your records"


def test_forget_refuses_a_manual_record_without_asking(home, manual, capsys):
    capsys.readouterr()
    assert cli.main(["forget", "help/", "shift"]) == 1, "nothing was forgotten"
    captured = capsys.readouterr()
    assert captured.err == "Not deleted: shift enter key is part of mash's manual\n", "it says why"
    assert "Continue?" not in captured.out, "and never asks"
    assert len(list((manual / "keys").glob("*.txt"))) == 1, "the file is still there"


def test_alfred_lists_help_as_a_folder(home, manual, capsys):
    capsys.readouterr()
    cli.main(["--alfred", ""])
    titles = [item["title"] for item in json.loads(capsys.readouterr().out)["items"]]
    assert titles[:2] == ["body/", "help/"], "the manual is a folder next to your own"
    assert "shift enter key" not in titles, "but its records are not in the bare list"


@pytest.mark.parametrize(
    "argv, line",
    [
        (["brain"], "  body  ·  2 records · last used 2026-11-01  #body"),
        (["brain"], "    weight  ·  ~> weight kg"),
        (["brain", "--facts"], "  ssh prod web  ·  ssh deploy@10.0.1.5"),
        (["brain", "--facts"], "    weight kg #body  ·  80  #body"),
    ],
)
def test_brain_prints_the_plan_as_an_outline(home_on_the_first_of_november, capsys, argv, line):
    capsys.readouterr()
    assert cli.main(argv) == 0, "showing the plan always succeeds"
    assert line in capsys.readouterr().out.splitlines(), f"{argv} should print {line!r}"


def test_brain_leaves_the_built_in_manual_out(home, capsys):
    capsys.readouterr()
    cli.main(["brain", "--facts"])
    assert "  help" not in capsys.readouterr().out, "the manual is mash's, not part of your tree"


def test_brain_sync_needs_a_key(home, capsys, monkeypatch, mocker):
    monkeypatch.delenv("MASH_BRAIN_KEY", raising=False)
    run = mocker.patch("mash.brainsync.run")
    assert cli.main(["brain", "sync"]) == 1, "without a key nothing can be sent"
    assert "MASH_BRAIN_KEY" in capsys.readouterr().err, "and the message names the setting"
    run.assert_not_called()


@pytest.mark.parametrize(
    "argv, prune, facts",
    [
        (["brain", "sync"], False, False),
        (["brain", "sync", "--prune"], True, False),
        (["brain", "sync", "--facts"], False, True),
    ],
)
def test_brain_sync_hands_the_plan_and_settings_over(home, monkeypatch, mocker, argv, prune, facts):
    from mash.brainsync import Report

    monkeypatch.setenv("MASH_BRAIN_KEY", "secret")
    monkeypatch.setenv("MASH_BRAIN_ID", "mine")
    monkeypatch.setenv("MASH_BRAIN_URL", "http://localhost:9")
    run = mocker.patch("mash.brainsync.run", return_value=Report(0, 0, 0, 0, 0, 0))
    assert cli.main(argv) == 0, "a sync that went through exits 0"
    plan, folder, key, brain_id, url, pruning = run.call_args.args
    assert (folder, key, brain_id, url) == (str(home), "secret", "mine", "http://localhost:9"), (
        "the tree's folder and the three settings are passed on"
    )
    assert pruning is prune, f"{argv} should prune: {prune}"
    assert (
        "record:" in " ".join(t.key for t in plan.thoughts if t.type == "type:fact")
    ) is facts, f"{argv} should plan facts: {facts}"


@pytest.mark.parametrize(
    "report, printed",
    [
        ((6, 1, 0, 6, 2, 0), "TheBrain: 6 created, 1 updated, 6 linked, 2 unlinked, 0 removed\n"),
        (
            (0, 0, 0, 0, 0, 2),
            "TheBrain: 0 created, 0 updated, 0 linked, 0 unlinked, 0 removed\n"
            "2 thoughts are no longer in mash; mash brain sync --prune deletes them\n",
        ),
        (
            (0, 0, 0, 0, 0, 1),
            "TheBrain: 0 created, 0 updated, 0 linked, 0 unlinked, 0 removed\n"
            "1 thought is no longer in mash; mash brain sync --prune deletes it\n",
        ),
    ],
)
def test_brain_sync_reports_what_changed(home, monkeypatch, mocker, capsys, report, printed):
    from mash.brainsync import Report

    monkeypatch.setenv("MASH_BRAIN_KEY", "secret")
    mocker.patch("mash.brainsync.run", return_value=Report(*report))
    capsys.readouterr()
    cli.main(["brain", "sync"])
    assert capsys.readouterr().out == printed, f"{report} should be reported as {printed!r}"


def test_brain_sync_reports_a_failure_and_exits_one(home, monkeypatch, mocker, capsys):
    from mash.brainsync import BrainError

    monkeypatch.setenv("MASH_BRAIN_KEY", "secret")
    mocker.patch("mash.brainsync.run", side_effect=BrainError("TheBrain is not answering"))
    assert cli.main(["brain", "sync"]) == 1, "a failed sync exits 1"
    assert "not answering" in capsys.readouterr().err, "and says why"


def test_act_prints_nothing_when_there_is_nothing_to_say(home, capsys):
    capsys.readouterr()
    assert cli.main(["--act", json.dumps({"do": "nothing"})]) == 0, "keeping a node is a success"
    assert capsys.readouterr().out == "", "an empty output is what keeps Alfred from notifying"


def test_prompt_serves_the_confirm_step(home, capsys):
    capsys.readouterr()
    cli.main(["--prompt", json.dumps({"do": "prompt", "ask": "forget_node", "node": "body"}), ""])
    titles = [item["title"] for item in json.loads(capsys.readouterr().out)["items"]]
    assert titles == ["Keep body/", "Delete body/ and its 2 records"], (
        "the prompt filter should list the two answers"
    )


@pytest.mark.parametrize("node", [".git", "..", "nowhere"])
def test_forget_node_refuses_a_folder_that_is_not_a_node(home, capsys, monkeypatch, node):
    (home / ".git").mkdir()
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("y\n"))
    assert cli.main(["forget", "--node", node]) == 1, f"{node} is not a node"
    assert f"no node {node}/" in capsys.readouterr().err, "and the message says so"
    assert (home / ".git").exists() and home.exists(), "nothing is removed"


def test_forget_node_says_what_it_removed(home, capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("y\n"))
    cli.main(["forget", "--node", "body/"])
    assert "Deleted node: body/ (2 records)" in capsys.readouterr().out, (
        "both surfaces report a node's removal the same way"
    )
