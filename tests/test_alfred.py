import json
import os

import pytest

from mash import alfred
from mash.journal import Journal
from mash.records import from_box
from mash.session import Session, Settings
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
    return Session(tree, Journal(os.path.join(root, ".journal.log")), Settings())


def items(session, text):
    return alfred.items(session, text)


def titles(result):
    return [item["title"] for item in result["items"]]


def command(item, mod=None):
    arg = item["mods"][mod]["arg"] if mod else item["arg"]
    return json.loads(arg)


def test_matches_then_add_row(home):
    result = items(home, "prod")
    assert titles(result) == ["ssh prod web", "Add: prod"], "hits come first, Add last"


def test_no_match_offers_only_add(home):
    result = items(home, "zzz")
    assert titles(result) == ["Add: zzz"], "a miss is an Add away from being stored"


def test_arrow_moves_add_to_the_top(home):
    result = items(home, "ssh prod web -> ssh other")
    assert titles(result)[0] == "Add: ssh prod web -> ssh other", "typing an arrow means adding"
    assert "ssh prod web" in titles(result), "the head words are still searched"


def test_add_row_names_the_node(home):
    result = items(home, "work/ k8 ctx -> kubectl")
    assert titles(result)[0] == "Add to work/: k8 ctx -> kubectl", "the row says where it adds"
    assert command(result["items"][0]) == {
        "do": "add",
        "node": "work",
        "text": "k8 ctx -> kubectl",
    }, "the add command carries node and text"


def test_several_node_terms_compose_into_a_path(home):
    result = items(home, "rain/ pain/ main/ deep -> x")
    assert titles(result)[0] == "Add to rain/pain/main/ (new node): deep -> x"
    alfred.act(home, command(result["items"][0]))
    assert titles(items(home, "rain/pain/main/"))[0] == "deep", "the record landed three deep"
    assert titles(items(home, "rain/"))[0] == "rain/pain/", "and the folders exist on the way"


def test_add_row_says_when_the_node_is_new(home):
    result = items(home, "new/ thing -> x")
    assert "(new node)" in result["items"][0]["title"], "adding into a missing node says so"


def test_empty_query_lists_root_folders_then_everything(home):
    result = items(home, "")
    assert titles(result)[:2] == ["body/", "work/"], "the root's folders come first, sorted"
    assert len(result["items"]) == 2 + 7 + 1, "then every record, then Add"
    assert "work/k8s/" not in titles(result), "only direct children, not grandchildren"


def test_empty_query_inside_a_node_lists_its_folders(home):
    result = items(home, "work/")
    assert titles(result)[0] == "work/k8s/", "inside work/, its own folders come first"


def test_empty_folders_are_listed_too(home):
    import os

    os.makedirs(os.path.join(home.tree.root, "empty"))
    row = next(i for i in items(home, "")["items"] if i["title"] == "empty/")
    assert row["subtitle"].startswith("0 records"), "a folder with no records still shows"


def test_empty_folder_is_offered_by_prefix_too(home):
    import os

    os.makedirs(os.path.join(home.tree.root, "empty"))
    assert titles(items(home, "em"))[0] == "empty/", "an empty folder is a node like any other"


def test_adding_into_an_existing_empty_folder_is_not_a_new_node(home):
    import os

    os.makedirs(os.path.join(home.tree.root, "empty"))
    assert titles(items(home, "empty/ x -> y"))[0] == "Add to empty/: x -> y", (
        "the folder exists, so the add row must not call it new"
    )


def test_node_row_offers_autocomplete(home):
    result = items(home, "wo")
    row = result["items"][0]
    assert row["title"] == "work/", "a node whose name starts with the query gets a row"
    assert row["autocomplete"] == "work/ ", "↩ or ⇥ should put the node into the query"
    assert row["valid"] is False, "the node row is not actionable itself"
    assert "1 record" in row["subtitle"], "the row says how many records the subtree holds"


def test_inside_a_node_only_its_subtree_shows(home):
    result = items(home, "work/")
    assert titles(result) == ["work/k8s/", "ctx staging", "Add to work/: "], (
        "work/ shows its folders and its subtree"
    )


def test_fact_row_command_and_subtitle(home):
    row = items(home, "prod")["items"][0]
    assert row["subtitle"] == "ssh deploy@10.0.1.5", "a fact previews its first body line"
    cmd = command(row)
    assert cmd["do"] == "act" and cmd["mode"] == "copy", "↩ acts on the record"
    assert "/ssh-prod-web." in cmd["path"], "the command names the file"
    assert command(row, "shift")["mode"] == "paste", "⇧↩ pastes"
    assert command(row, "cmd")["mode"] == "edit", "⌘↩ edits"
    assert command(row, "alt")["mode"] == "delete", "⌥↩ deletes"


def test_open_subtitle_for_urls(home):
    row = items(home, "grafana")["items"][0]
    assert row["subtitle"].startswith("Open · "), "a URL says it will open"


def test_rule_row_shows_its_query(home):
    row = items(home, "weight")["items"][0]
    assert row["title"] == "weight", "the tighter head wins"
    assert row["subtitle"] == "~> weight kg", "a rule shows arrow and query"


def test_handoff_subtitle(home):
    row = items(home, "delany")["items"][0]
    assert row["subtitle"] == "→ kb · delany", "a hand-off says where it goes"


def test_placeholder_preview_in_subtitle(home, mocker):
    mocker.patch("mash.fill.today", return_value="2026-11-01")
    home.tree.add("", from_box("stamp -> {{date}} note"))
    row = items(home, "stamp")["items"][0]
    assert row["subtitle"] == "2026-11-01 note", "date fills in the preview"


def test_run_row_for_usable_text_with_matches(home):
    result = items(home, "delany @kobold")
    assert titles(result) == ["delany books", "Run: delany @kobold", "Add: delany @kobold"], (
        "usable text with a hit gets a Run row between hits and Add"
    )
    assert command(result["items"][1]) == {"do": "run", "text": "delany @kobold"}


def test_no_run_row_without_matches(home):
    result = items(home, "https://example.com/zzz")
    assert titles(result) == ["Add: https://example.com/zzz"], "no hit means no Run row"


def test_max_results_caps_rows(home):
    session = Session(home.tree, home.journal, Settings(max_results=2))
    result = items(session, "")
    assert len(result["items"]) == 2 + 2 + 1, "root folders, max_results hits, Add"


def test_act_copy_touches_the_journal(home, mocker):
    perform = mocker.patch("mash.session.actions.perform")
    row = items(home, "prod")["items"][0]
    message = alfred.act(home, command(row))
    perform.assert_called_once()
    assert perform.call_args[0][0].target == "ssh deploy@10.0.1.5", "copy the body"
    assert message == "Copied: ssh deploy@10.0.1.5", "the notification shows the value"
    assert home.journal.touched(), "↩ is a touch"


def test_act_resolves_a_rule_and_touches_every_step(home, mocker):
    mocker.patch("mash.session.actions.perform")
    row = items(home, "weight")["items"][0]
    message = alfred.act(home, command(row))
    assert message == "weight → weight kg #body → 80", "the chain is shown"
    assert len(home.journal.touched()) == 2, "resolution touches the rule and the fact"


def test_act_with_blanks_asks_before_doing(home, mocker):
    perform = mocker.patch("mash.session.actions.perform")
    row = items(home, "box")["items"][0]
    cmd = command(row)
    assert cmd["do"] == "prompt", "a record with blanks prompts first"
    perform.assert_not_called()


def test_prompt_rows_and_progression(home, mocker):
    mocker.patch("mash.session.read_clipboard", return_value="10.0.0.9")
    row = items(home, "box")["items"][0]
    first = alfred.prompt(home, command(row), "")
    assert [i["title"] for i in first["items"]] == ["user (1/2): root", "user (1/2): 10.0.0.9"], (
        "first prompt offers the default and the clipboard"
    )
    assert first["items"][0]["subtitle"] == "ssh root@{{host}}", "the subtitle shows progress"
    second = alfred.prompt(home, command(first["items"][0]), "db")
    assert [i["title"] for i in second["items"]][:2] == [
        "host (2/2): db",
        "host (2/2): 10.0.0.9",
    ], "typed text comes first on the next blank"
    final = command(second["items"][0])
    assert final["do"] == "act" and final["values"] == {"user": "root", "host": "db"}, (
        "the last choice turns into an act with all values"
    )


def test_act_with_values_fills_then_copies(home, mocker):
    perform = mocker.patch("mash.session.actions.perform")
    row = items(home, "box")["items"][0]
    cmd = dict(command(row), do="act", mode="copy", values={"user": "root", "host": "db"})
    message = alfred.act(home, cmd)
    assert perform.call_args[0][0].target == "ssh root@db", "blanks are filled before acting"
    assert message == "Copied: ssh root@db"


def test_act_delete_removes_file_and_journal(home, mocker):
    row = items(home, "prod")["items"][0]
    identity = home.tree.read(command(row)["path"]).identity
    home.journal.touch(identity, "copy")
    message = alfred.act(home, command(row, "alt"))
    assert message == "Deleted: ssh prod web"
    assert titles(items(home, "prod")) == ["Add: prod"], "the record is gone"
    assert identity not in home.journal.touched(), "and so is its history"


def test_act_edit_runs_the_editor(home, mocker):
    run = mocker.patch("subprocess.run")
    session = Session(home.tree, home.journal, Settings(editor="code -g {file}"))
    row = items(session, "prod")["items"][0]
    cmd = command(row, "cmd")
    alfred.act(session, cmd)
    assert run.call_args[0][0] == ["code", "-g", cmd["path"]], "the editor command gets the file"


def test_act_add_writes_and_reports(home):
    message = alfred.act(home, {"do": "add", "node": "work", "text": "k8 ctx -> kubectl"})
    assert message == "Added to work/: k8 ctx"
    assert titles(items(home, "work/ k8"))[0] == "k8 ctx", "the new record is found"


def test_act_run_acts_on_the_text_without_storing(home, mocker):
    perform = mocker.patch("mash.session.actions.perform")
    alfred.act(home, {"do": "run", "text": "delany @kobold"})
    assert perform.call_args[0][0].kind == "handoff"
    assert titles(items(home, "kobold")) == ["Add: kobold"], "nothing was stored"


def node_item(session, text, title):
    return next(item for item in items(session, text)["items"] if item["title"] == title)


@pytest.mark.parametrize(
    "text, title, node",
    [("", "body/", "body"), ("", "work/", "work"), ("work/", "work/k8s/", "work/k8s")],
)
def test_opt_enter_on_a_node_row_asks_to_delete_it(home, text, title, node):
    alt = node_item(home, text, title)["mods"]["alt"]
    assert json.loads(alt["arg"]) == {"do": "prompt", "ask": "forget_node", "node": node}, (
        f"⌥↩ on {title} should open the confirm step for {node}"
    )
    assert alt["valid"] is True, "the mod acts although the row itself only completes"
    assert alt["variables"] == {"prompt": "1"}, "and it goes through the prompt filter, not to act"
    assert alt["subtitle"] == f"Delete {title} and everything in it: asks first", (
        "holding ⌥ should say what ↩ would start"
    )


def test_a_node_row_still_only_completes_on_plain_enter(home):
    row = node_item(home, "", "work/")
    assert row["valid"] is False and "arg" not in row, "↩ on a folder walks in, it does not act"


@pytest.mark.parametrize(
    "node, question",
    [
        ("body", "Delete body/ and its 2 records"),
        ("work", "Delete work/ and its 1 record"),
        ("work/k8s", "Delete work/k8s/ and its 1 record"),
        ("spare", "Delete spare/, which is empty"),
    ],
)
def test_the_confirm_step_offers_keeping_first_then_deleting(home, node, question):
    os.makedirs(os.path.join(home.tree.root, "spare"))
    asked = alfred.prompt(home, {"do": "prompt", "ask": "forget_node", "node": node}, "")["items"]
    assert [item["title"] for item in asked] == [f"Keep {node}/", question], (
        "a second ↩ should be harmless; deleting takes ↓ first"
    )
    assert [json.loads(item["arg"]) for item in asked] == [
        {"do": "nothing"},
        {"do": "forget_node", "node": node},
    ], "each answer carries what act should do"
    assert [item["variables"] for item in asked] == [{"more": "0"}] * 2, (
        "either answer ends the prompt loop"
    )


def test_the_delete_answer_warns_that_it_cannot_be_undone(home):
    asked = alfred.prompt(home, {"do": "prompt", "ask": "forget_node", "node": "body"}, "")
    assert "no undo" in asked["items"][1]["subtitle"], "the last thing read before ↩ is the warning"


@pytest.mark.parametrize("typed", ["", "y", "body", "anything at all"])
def test_typing_in_the_confirm_step_changes_nothing(home, typed):
    command = {"do": "prompt", "ask": "forget_node", "node": "body"}
    assert alfred.prompt(home, command, typed) == alfred.prompt(home, command, ""), (
        f"{typed!r} is not an answer; the two rows are"
    )


@pytest.mark.parametrize("node", ["nowhere", "", "..", ".git", "body/../work"])
def test_the_confirm_step_offers_no_delete_for_what_is_not_a_node(home, node):
    os.makedirs(os.path.join(home.tree.root, ".git"))
    asked = alfred.prompt(home, {"do": "prompt", "ask": "forget_node", "node": node}, "")["items"]
    assert [json.loads(item["arg"]) for item in asked] == [{"do": "nothing"}], (
        f"{node!r} is not one of the tree's folders, so there is nothing to confirm"
    )


@pytest.mark.parametrize(
    "node, message, gone, kept",
    [
        ("body", "Deleted node: body/ (2 records)", ["body"], ["work/k8s"]),
        ("work", "Deleted node: work/ (1 record)", ["work", "work/k8s"], ["body"]),
        ("work/k8s", "Deleted node: work/k8s/ (1 record)", ["work/k8s"], ["work", "body"]),
    ],
)
def test_act_forget_node_removes_the_folder_and_everything_under_it(
    home, node, message, gone, kept
):
    assert alfred.act(home, {"do": "forget_node", "node": node}) == message, "act says what went"
    left = home.tree.load().folders
    assert not set(gone) & set(left), f"{gone} should be gone"
    assert set(kept) <= set(left), f"{kept} should be untouched"
    assert len(home.tree.load().records) == 7 - int(message.split("(")[1].split()[0]), (
        "only that node's records go"
    )


def test_act_forget_node_drops_the_journal_lines_under_it(home):
    inside = next(s for s in home.tree.load().records if s.node == "work/k8s")
    outside = next(s for s in home.tree.load().records if s.node == "body")
    home.touch_chain([inside, outside], "copy")
    alfred.act(home, {"do": "forget_node", "node": "work"})
    touched = home.journal.touched()
    assert inside.identity not in touched, "history under the node goes with it"
    assert outside.identity in touched, "history elsewhere stays"


@pytest.mark.parametrize(
    "node, message",
    [
        ("nowhere", "Not deleted: there is no node nowhere/"),
        ("", "Not deleted: there is no node /"),
        ("..", "Not deleted: there is no node ../"),
        (".git", "Not deleted: there is no node .git/"),
        ("body/../work", "Not deleted: there is no node body/../work/"),
    ],
)
def test_act_forget_node_refuses_what_is_not_a_node(home, node, message):
    os.makedirs(os.path.join(home.tree.root, ".git"))
    home.tree.load()
    before = sorted(os.listdir(home.tree.root))
    assert alfred.act(home, {"do": "forget_node", "node": node}) == message, "act says why not"
    assert sorted(os.listdir(home.tree.root)) == before, "and the tree is as it was"


def test_act_nothing_does_nothing_and_says_nothing(home):
    before = home.tree.load()
    assert alfred.act(home, {"do": "nothing"}) == "", "keeping needs no notification"
    assert home.tree.load() == before, "and changes nothing"
