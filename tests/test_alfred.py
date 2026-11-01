import json
import os

import pytest

from mash import alfred
from mash.journal import Journal
from mash.records import from_box
from mash.tree import Tree


@pytest.fixture
def home(tmp_path):
    root = str(tmp_path / "mash")
    tree = Tree(root)
    tree.add("", from_box("ssh prod web -> ssh deploy@10.0.1.5"))
    tree.add("", from_box("grafana latency -> https://grafana.example.com/d/x"))
    tree.add("", from_box("ssh box -> ssh {{user=root}}@{{host}}"))
    tree.add("body", from_box("weight kg #body -> 80"))
    tree.add("body", from_box("weight ~> weight kg"))
    tree.add("work/k8s", from_box("ctx staging -> kubectl config use-context staging"))
    tree.add("", from_box("delany books -> delany @kb"))
    return alfred.Session(tree, Journal(os.path.join(root, ".journal.log")), alfred.Settings())


def titles(result):
    return [item["title"] for item in result["items"]]


def command(item, mod=None):
    arg = item["mods"][mod]["arg"] if mod else item["arg"]
    return json.loads(arg)


def test_matches_then_add_row(home):
    result = home.items("prod")
    assert titles(result) == ["ssh prod web", "Add: prod"], "hits come first, Add last"


def test_no_match_offers_only_add(home):
    result = home.items("zzz")
    assert titles(result) == ["Add: zzz"], "a miss is an Add away from being stored"


def test_arrow_moves_add_to_the_top(home):
    result = home.items("ssh prod web -> ssh other")
    assert titles(result)[0] == "Add: ssh prod web -> ssh other", "typing an arrow means adding"
    assert "ssh prod web" in titles(result), "the head words are still searched"


def test_add_row_names_the_node(home):
    result = home.items("work/ k8 ctx -> kubectl")
    assert titles(result)[0] == "Add to work/: k8 ctx -> kubectl", "the row says where it adds"
    assert command(result["items"][0]) == {
        "do": "add",
        "node": "work",
        "text": "k8 ctx -> kubectl",
    }, "the add command carries node and text"


def test_add_row_says_when_the_node_is_new(home):
    result = home.items("new/ thing -> x")
    assert "(new node)" in result["items"][0]["title"], "adding into a missing node says so"


def test_empty_query_browses_everything(home):
    result = home.items("")
    assert len(result["items"]) == 7 + 1, "every record plus Add"


def test_node_row_offers_autocomplete(home):
    result = home.items("wo")
    row = result["items"][0]
    assert row["title"] == "work/", "a node whose name starts with the query gets a row"
    assert row["autocomplete"] == "work/ ", "↩ or ⇥ should put the node into the query"
    assert row["valid"] is False, "the node row is not actionable itself"
    assert "1 record" in row["subtitle"], "the row says how many records the subtree holds"


def test_inside_a_node_only_its_subtree_shows(home):
    result = home.items("work/")
    assert titles(result) == ["ctx staging", "Add to work/: "], "work/ shows only its subtree"


def test_fact_row_command_and_subtitle(home):
    row = home.items("prod")["items"][0]
    assert row["subtitle"] == "ssh deploy@10.0.1.5", "a fact previews its first body line"
    cmd = command(row)
    assert cmd["do"] == "act" and cmd["mode"] == "copy", "↩ acts on the record"
    assert cmd["path"].endswith("ssh-prod-web.txt"), "the command names the file"
    assert command(row, "shift")["mode"] == "paste", "⇧↩ pastes"
    assert command(row, "cmd")["mode"] == "edit", "⌘↩ edits"
    assert command(row, "alt")["mode"] == "delete", "⌥↩ deletes"


def test_open_subtitle_for_urls(home):
    row = home.items("grafana")["items"][0]
    assert row["subtitle"].startswith("Open · "), "a URL says it will open"


def test_rule_row_shows_its_query(home):
    row = home.items("weight")["items"][0]
    assert row["title"] == "weight", "the tighter head wins"
    assert row["subtitle"] == "~> weight kg", "a rule shows arrow and query"


def test_handoff_subtitle(home):
    row = home.items("delany")["items"][0]
    assert row["subtitle"] == "→ kb · delany", "a hand-off says where it goes"


def test_placeholder_preview_in_subtitle(home, mocker):
    mocker.patch("mash.fill.today", return_value="2026-11-01")
    home.tree.add("", from_box("stamp -> {{date}} note"))
    row = home.items("stamp")["items"][0]
    assert row["subtitle"] == "2026-11-01 note", "date fills in the preview"


def test_run_row_for_usable_text_with_matches(home):
    result = home.items("delany @kobold")
    assert titles(result) == ["delany books", "Run: delany @kobold", "Add: delany @kobold"], (
        "usable text with a hit gets a Run row between hits and Add"
    )
    assert command(result["items"][1]) == {"do": "run", "text": "delany @kobold"}


def test_no_run_row_without_matches(home):
    result = home.items("https://example.com/zzz")
    assert titles(result) == ["Add: https://example.com/zzz"], "no hit means no Run row"


def test_max_results_caps_rows(home):
    session = alfred.Session(home.tree, home.journal, alfred.Settings(max_results=2))
    result = session.items("")
    assert len(result["items"]) == 3, "max_results hits plus Add"


def test_act_copy_touches_the_journal(home, mocker):
    perform = mocker.patch("mash.alfred.actions.perform")
    row = home.items("prod")["items"][0]
    message = home.act(command(row))
    perform.assert_called_once()
    assert perform.call_args[0][0].target == "ssh deploy@10.0.1.5", "copy the body"
    assert message == "Copied: ssh deploy@10.0.1.5", "the notification shows the value"
    assert ("", "ssh prod web") in home.journal.touched(), "↩ is a touch"


def test_act_resolves_a_rule_and_touches_every_step(home, mocker):
    mocker.patch("mash.alfred.actions.perform")
    row = home.items("weight")["items"][0]
    message = home.act(command(row))
    assert message == "weight → weight kg #body → 80", "the chain is shown"
    touched = home.journal.touched()
    assert ("body", "weight") in touched and ("body", "weight kg #body") in touched, (
        "resolution touches the rule and the fact"
    )


def test_act_with_blanks_asks_before_doing(home, mocker):
    perform = mocker.patch("mash.alfred.actions.perform")
    row = home.items("box")["items"][0]
    cmd = command(row)
    assert cmd["do"] == "prompt", "a record with blanks prompts first"
    perform.assert_not_called()


def test_prompt_rows_and_progression(home, mocker):
    mocker.patch("mash.alfred.read_clipboard", return_value="10.0.0.9")
    row = home.items("box")["items"][0]
    first = home.prompt(command(row), "")
    assert [i["title"] for i in first["items"]] == ["user (1/2): root", "user (1/2): 10.0.0.9"], (
        "first prompt offers the default and the clipboard"
    )
    assert first["items"][0]["subtitle"] == "ssh root@{{host}}", "the subtitle shows progress"
    second = home.prompt(command(first["items"][0]), "db")
    assert [i["title"] for i in second["items"]][:2] == [
        "host (2/2): db",
        "host (2/2): 10.0.0.9",
    ], "typed text comes first on the next blank"
    final = command(second["items"][0])
    assert final["do"] == "act" and final["values"] == {"user": "root", "host": "db"}, (
        "the last choice turns into an act with all values"
    )


def test_act_with_values_fills_then_copies(home, mocker):
    perform = mocker.patch("mash.alfred.actions.perform")
    row = home.items("box")["items"][0]
    cmd = dict(command(row), do="act", mode="copy", values={"user": "root", "host": "db"})
    message = home.act(cmd)
    assert perform.call_args[0][0].target == "ssh root@db", "blanks are filled before acting"
    assert message == "Copied: ssh root@db"


def test_act_delete_removes_file_and_journal(home, mocker):
    row = home.items("prod")["items"][0]
    home.journal.touch("", "ssh prod web", "copy")
    message = home.act(command(row, "alt"))
    assert message == "Deleted: ssh prod web"
    assert titles(home.items("prod")) == ["Add: prod"], "the record is gone"
    assert ("", "ssh prod web") not in home.journal.touched(), "and so is its history"


def test_act_edit_runs_the_editor(home, mocker):
    run = mocker.patch("subprocess.run")
    session = alfred.Session(home.tree, home.journal, alfred.Settings(editor="code -g {file}"))
    row = session.items("prod")["items"][0]
    cmd = command(row, "cmd")
    session.act(cmd)
    assert run.call_args[0][0] == ["code", "-g", cmd["path"]], "the editor command gets the file"


def test_act_add_writes_and_reports(home):
    message = home.act({"do": "add", "node": "work", "text": "k8 ctx -> kubectl"})
    assert message == "Added to work/: k8 ctx"
    assert titles(home.items("work/ k8"))[0] == "k8 ctx", "the new record is found"


def test_act_run_acts_on_the_text_without_storing(home, mocker):
    perform = mocker.patch("mash.alfred.actions.perform")
    home.act({"do": "run", "text": "delany @kobold"})
    assert perform.call_args[0][0].kind == "handoff"
    assert titles(home.items("kobold")) == ["Add: kobold"], "nothing was stored"
