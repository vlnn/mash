import http.server
import io
import json
import threading
import urllib.error

import pytest

from mash import brainsync
from mash.brain import CHILD, JUMP, TAG, TAGGED, TYPE, Link, Plan, Thought
from mash.brainsync import BrainError, Remote, Report

BRAIN = "b0000000-0000-0000-0000-00000000000b"
HOME = "h0000000-0000-0000-0000-00000000000h"
ZERO = "00000000-0000-0000-0000-000000000000"

RULE_TYPE = Thought("type:rule", "mash rule", TYPE)
READING = Thought("tag:#reading", "#reading", TAG)
ROOT = Thought("node:", "mash", label="2 records", note="- **a**")
WORK = Thought("node:work", "work", label="1 record")
RULE = Thought("record:aaaaaa", "k8", type="type:rule", label="=> kube", note="`k8 => kube`")
LINKED = Thought("record:bbbbbb", "grafana", url="https://grafana.example.com")

PLAN = Plan(
    (RULE_TYPE, READING, ROOT, WORK, RULE, LINKED),
    (
        Link("node:", "node:work", CHILD),
        Link("node:work", "record:aaaaaa", CHILD),
        Link("node:", "record:bbbbbb", CHILD),
        Link("record:aaaaaa", "tag:#reading", TAGGED),
        Link("record:aaaaaa", "node:", JUMP, "=>"),
    ),
)


class FakeBrain:
    def __init__(self, link_answer=None):
        self.requests = []
        self.link_answer = link_answer

    def __call__(self, method, path, body=None, query=None):
        self.requests.append((method, path, body, query))
        if (method, path) == ("GET", f"/api/brains/{BRAIN}"):
            return {"id": BRAIN, "name": "Mine", "homeThoughtId": HOME}
        if method == "POST" and path == f"/api/links/{BRAIN}" and self.link_answer:
            return {"id": self.link_answer}
        if method == "POST" and path.startswith(("/api/thoughts/", "/api/links/")):
            return {"id": f"id-{len(self.requests)}"}
        return None

    def sent(self, method, start=""):
        return [r for r in self.requests if r[0] == method and r[1].startswith(start)]

    def writes(self):
        return [r for r in self.requests if r[0] != "GET"]


@pytest.fixture
def fake():
    return FakeBrain()


@pytest.fixture
def state():
    return brainsync.new_state(BRAIN)


@pytest.fixture
def synced(fake, state):
    brainsync.sync(PLAN, state, Remote(fake, BRAIN))
    fake.requests.clear()
    return state


def sync(plan, state, fake, **options):
    return brainsync.sync(plan, state, Remote(fake, BRAIN), **options)


def replaced(plan, old, new):
    return Plan(tuple(new if t == old else t for t in plan.thoughts), plan.links)


def without(plan, key):
    thoughts = tuple(t for t in plan.thoughts if t.key != key)
    links = tuple(link for link in plan.links if key not in (link.source, link.target))
    return Plan(thoughts, links)


def id_of(state, key):
    return state["thoughts"][key]["id"]


def test_first_sync_creates_every_thought_and_link(fake, state):
    report = sync(PLAN, state, fake)
    assert report == Report(created=6, updated=0, removed=0, linked=6, unlinked=0, stale=0), (
        "six thoughts, their five links, and the one that hangs the root under home"
    )


@pytest.mark.parametrize(
    "thought, body",
    [
        (ROOT, {"name": "mash", "kind": 1, "acType": 0, "label": "2 records"}),
        (READING, {"name": "#reading", "kind": 4, "acType": 0}),
        (RULE_TYPE, {"name": "mash rule", "kind": 2, "acType": 0}),
    ],
)
def test_a_thought_is_posted_with_its_kind_and_label(fake, state, thought, body):
    sync(PLAN, state, fake)
    posted = [r[2] for r in fake.sent("POST", f"/api/thoughts/{BRAIN}")]
    assert body in posted, f"{thought.key} should be created as {body}"


def test_a_typed_thought_names_its_type_by_id(fake, state):
    sync(PLAN, state, fake)
    posted = next(r[2] for r in fake.sent("POST", "/api/thoughts/") if r[2]["name"] == "k8")
    assert posted["typeId"] == id_of(state, "type:rule"), (
        "the rule should be created under its type"
    )


def test_types_are_created_before_the_thoughts_that_use_them(fake, state):
    late = Plan((RULE, RULE_TYPE, ROOT, WORK, READING, LINKED), PLAN.links)
    sync(late, state, fake)
    names = [r[2]["name"] for r in fake.sent("POST", "/api/thoughts/")]
    assert names.index("mash rule") < names.index("k8"), "a type id has to exist before it is used"


def test_a_note_is_written_as_markdown(fake, state):
    sync(PLAN, state, fake)
    path = f"/api/notes/{BRAIN}/{id_of(state, 'node:')}/update"
    assert ("POST", path, {"markdown": "- **a**"}, None) in fake.requests, (
        "the root's listing should become its note"
    )


def test_a_thought_without_a_note_gets_none(fake, state):
    sync(PLAN, state, fake)
    assert not fake.sent("POST", f"/api/notes/{BRAIN}/{id_of(state, 'node:work')}"), (
        "an empty note is not worth a request"
    )


def test_a_link_body_becomes_a_url_attachment(fake, state):
    sync(PLAN, state, fake)
    path = f"/api/attachments/{BRAIN}/{id_of(state, 'record:bbbbbb')}/url"
    query = {"url": "https://grafana.example.com", "name": "grafana"}
    assert ("POST", path, None, query) in fake.requests, "a URL should be clickable in TheBrain"


@pytest.mark.parametrize(
    "source, target, relation, name, why",
    [
        ("node:", "node:work", 1, None, "a child link runs from the parent, relation 1"),
        ("record:aaaaaa", "node:", 3, "=>", "a jump is relation 3 and carries the arrow"),
        ("record:aaaaaa", "tag:#reading", 2, None, "a tag is attached as the thought's parent"),
    ],
)
def test_links_are_posted_by_thought_id(fake, state, source, target, relation, name, why):
    sync(PLAN, state, fake)
    body = {
        "thoughtIdA": id_of(state, source),
        "thoughtIdB": id_of(state, target),
        "relation": relation,
    }
    if name:
        body["name"] = name
    assert ("POST", f"/api/links/{BRAIN}", body, None) in fake.requests, why


def test_the_root_hangs_under_the_home_thought(fake, state):
    sync(PLAN, state, fake)
    body = {"thoughtIdA": HOME, "thoughtIdB": id_of(state, "node:"), "relation": 1}
    assert ("POST", f"/api/links/{BRAIN}", body, None) in fake.requests, (
        "an unlinked root would be an orphan nobody finds"
    )


def test_syncing_an_unchanged_plan_sends_nothing(fake, synced):
    report = sync(PLAN, synced, fake)
    assert fake.requests == [], "a second sync of the same plan should not touch TheBrain"
    assert report == Report(0, 0, 0, 0, 0, 0), "and should report no change"


@pytest.mark.parametrize(
    "new, patch",
    [
        (
            WORK._replace(name="job"),
            [
                {"op": "replace", "path": "/name", "value": "job"},
                {"op": "replace", "path": "/label", "value": "1 record"},
            ],
        ),
        (
            WORK._replace(label=""),
            [
                {"op": "replace", "path": "/name", "value": "work"},
                {"op": "remove", "path": "/label"},
            ],
        ),
    ],
    ids=["renamed", "label cleared"],
)
def test_a_changed_title_is_patched(fake, synced, new, patch):
    report = sync(replaced(PLAN, WORK, new), synced, fake)
    path = f"/api/thoughts/{BRAIN}/{id_of(synced, 'node:work')}"
    assert fake.requests == [("PATCH", path, patch, None)], "only the changed thought is patched"
    assert report.updated == 1, "one thought changed"


def test_a_changed_note_is_rewritten(fake, synced):
    sync(replaced(PLAN, ROOT, ROOT._replace(note="- **b**")), synced, fake)
    path = f"/api/notes/{BRAIN}/{id_of(synced, 'node:')}/update"
    assert fake.requests == [("POST", path, {"markdown": "- **b**"}, None)], (
        "a note is replaced whole, and nothing else is sent"
    )


def test_a_changed_url_is_attached(fake, synced):
    sync(replaced(PLAN, LINKED, LINKED._replace(url="https://new.example.com")), synced, fake)
    assert [r[3]["url"] for r in fake.requests] == ["https://new.example.com"], (
        "the new address should be attached"
    )


def test_a_moved_thought_is_relinked_not_recreated(fake, synced):
    old = Link("node:work", "record:aaaaaa", CHILD)
    new = Link("node:", "record:aaaaaa", CHILD)
    jump = Link("record:aaaaaa", "node:", JUMP, "=>")
    old_id = next(link["id"] for link in synced["links"] if link["target"] == "record:aaaaaa")
    moved = Plan(
        PLAN.thoughts, tuple(link for link in PLAN.links if link not in (old, jump)) + (new,)
    )
    report = sync(moved, synced, fake)
    assert ("DELETE", f"/api/links/{BRAIN}/{old_id}", None, None) in fake.requests, (
        "the link to the old node should go"
    )
    assert not fake.sent("POST", "/api/thoughts/"), "the thought keeps its id and its history"
    assert (report.linked, report.unlinked) == (1, 2), "the jump and the old parent go, one comes"


def test_links_are_removed_before_new_ones_are_made(fake, synced):
    jump = Link("record:aaaaaa", "node:", JUMP, "=>")
    retold = Plan(
        PLAN.thoughts, tuple(jump._replace(name="~>") if x == jump else x for x in PLAN.links)
    )
    sync(retold, synced, fake)
    assert [r[0] for r in fake.requests] == ["DELETE", "POST"], (
        "TheBrain keeps one link per pair, so the old one goes first"
    )


def test_a_vanished_record_is_kept_and_reported_without_prune(fake, synced):
    report = sync(without(PLAN, "record:aaaaaa"), synced, fake)
    assert fake.requests == [], "nothing is deleted from TheBrain unless asked"
    assert report.stale == 1, "the leftover thought should be counted"
    assert "record:aaaaaa" in synced["thoughts"], "and remembered, so a later prune finds it"


def test_prune_deletes_what_mash_no_longer_has(fake, synced):
    gone = id_of(synced, "record:aaaaaa")
    report = sync(without(PLAN, "record:aaaaaa"), synced, fake, prune=True)
    assert fake.requests == [("DELETE", f"/api/thoughts/{BRAIN}/{gone}", None, None)], (
        "deleting the thought takes its links along; they need no request of their own"
    )
    assert (report.removed, report.stale) == (1, 0), "one thought removed, none left over"
    assert "record:aaaaaa" not in synced["thoughts"], "the state should forget the thought"
    ends = [key for link in synced["links"] for key in (link["source"], link["target"])]
    assert "record:aaaaaa" not in ends, "and its links"


def test_prune_never_deletes_the_home_thought(fake, synced):
    sync(Plan((), ()), synced, fake, prune=True)
    assert HOME not in [r[1].rpartition("/")[2] for r in fake.sent("DELETE")], (
        "the home thought is the user's, not the mirror's"
    )


def test_a_link_answered_with_zeros_is_an_error(state):
    with pytest.raises(BrainError, match="did not make the link"):
        sync(PLAN, state, FakeBrain(link_answer=ZERO))


def test_what_was_created_before_a_failure_is_remembered(state):
    with pytest.raises(BrainError):
        sync(PLAN, state, FakeBrain(link_answer=ZERO))
    assert set(state["thoughts"]) == {t.key for t in PLAN.thoughts}, (
        "a rerun should not create the same thoughts twice"
    )


class FailsOnSecondDelete(FakeBrain):
    def __call__(self, method, path, body=None, query=None):
        if method == "DELETE" and self.sent("DELETE"):
            raise BrainError("TheBrain went away")
        return super().__call__(method, path, body, query)


@pytest.mark.parametrize(
    "plan, prune, what",
    [
        (Plan(PLAN.thoughts, ()), False, "links"),
        (Plan((), ()), True, "thoughts"),
    ],
    ids=["unlinking", "pruning"],
)
def test_a_removal_that_fails_halfway_forgets_only_what_it_removed(synced, plan, prune, what):
    before = len(synced[what])
    with pytest.raises(BrainError):
        sync(plan, synced, FailsOnSecondDelete(), prune=prune)
    assert len(synced[what]) == before - 1, f"one of the {what} went, so one should be forgotten"


def test_state_round_trips_through_its_file(tmp_path, synced):
    path = str(tmp_path / ".brain.json")
    brainsync.save_state(path, synced)
    assert brainsync.load_state(path, BRAIN) == synced, "what was saved is what is loaded"


def test_a_missing_state_file_starts_empty(tmp_path):
    assert brainsync.load_state(str(tmp_path / ".brain.json"), BRAIN) == brainsync.new_state(
        BRAIN
    ), "a first sync has nothing to remember"


def test_state_from_another_brain_is_refused(tmp_path, synced):
    path = str(tmp_path / ".brain.json")
    brainsync.save_state(path, synced)
    with pytest.raises(BrainError, match="another brain"):
        brainsync.load_state(path, "c0000000-0000-0000-0000-00000000000c")


@pytest.mark.parametrize(
    "brains, wanted, picked",
    [
        ([{"id": "one", "name": "A"}], "", "one"),
        ([{"id": "one", "name": "A"}, {"id": "two", "name": "B"}], "two", "two"),
        ([], "given", "given"),
    ],
)
def test_the_brain_is_the_one_asked_for_or_the_only_one(brains, wanted, picked):
    assert brainsync.pick_brain(brains, wanted) == picked, f"{wanted!r} among {brains} is {picked}"


def test_several_brains_and_no_choice_lists_them():
    brains = [{"id": "one", "name": "A"}, {"id": "two", "name": "B"}]
    with pytest.raises(BrainError, match="MASH_BRAIN_ID(.|\n)*one  A(.|\n)*two  B"):
        brainsync.pick_brain(brains, "")


class Answer(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


@pytest.fixture
def urlopen(mocker):
    return mocker.patch("urllib.request.urlopen", return_value=Answer(b'{"id": "x"}'))


@pytest.mark.parametrize(
    "method, body, query, url, content_type",
    [
        ("GET", None, None, "http://localhost:11522/api/brains", None),
        ("POST", {"name": "a"}, None, "http://localhost:11522/api/brains", "application/json"),
        (
            "PATCH",
            [{"op": "remove"}],
            None,
            "http://localhost:11522/api/brains",
            "application/json-patch+json",
        ),
        (
            "POST",
            None,
            {"url": "https://a.b/?c=d e"},
            "http://localhost:11522/api/brains?url=https%3A%2F%2Fa.b%2F%3Fc%3Dd+e",
            None,
        ),
    ],
    ids=["get", "post json", "patch json-patch", "query"],
)
def test_http_speaks_the_local_api(urlopen, method, body, query, url, content_type):
    send = brainsync.http("http://localhost:11522/api/", "secret")
    assert send(method, "/api/brains", body, query) == {"id": "x"}, "a JSON answer is parsed"
    request = urlopen.call_args.args[0]
    assert (request.get_method(), request.full_url) == (method, url), "method and address as asked"
    assert request.get_header("Authorization") == "Bearer secret", (
        "the key travels as a bearer token"
    )
    assert request.get_header("Content-type") == content_type, f"{method} body is {content_type}"
    assert request.data == (None if body is None else json.dumps(body).encode()), "the body is JSON"


@pytest.mark.parametrize(
    "answer, expected",
    [(b"", None), (b'[{"id": 1}]', [{"id": 1}]), (b"plain", "plain")],
)
def test_http_answers(mocker, answer, expected):
    mocker.patch("urllib.request.urlopen", return_value=Answer(answer))
    assert brainsync.http("http://x", "k")("GET", "/api/brains") == expected, (
        f"{answer!r} should be read as {expected!r}"
    )


def test_a_page_instead_of_data_is_an_error(mocker):
    mocker.patch("urllib.request.urlopen", return_value=Answer(b"<!doctype html><html>"))
    with pytest.raises(BrainError, match="a page"):
        brainsync.http("http://x", "k")("GET", "/api/thoughts/not-an-id")


def test_a_refusal_names_the_request_and_the_status(mocker):
    refusal = urllib.error.HTTPError("http://x", 401, "Unauthorized", {}, io.BytesIO(b"bad key"))
    mocker.patch("urllib.request.urlopen", side_effect=refusal)
    with pytest.raises(BrainError, match="GET /api/brains: 401 bad key"):
        brainsync.http("http://x", "k")("GET", "/api/brains")


def test_connect_falls_through_to_the_address_that_answers(mocker):
    down = urllib.error.URLError("refused")
    mocker.patch("urllib.request.urlopen", side_effect=[down, Answer(b'[{"id": "one"}]')])
    send, brains = brainsync.connect(("http://new", "http://old"), "k")
    assert brains == [{"id": "one"}], "the second address answered"
    mocker.patch("urllib.request.urlopen", return_value=Answer(b"{}"))
    send("GET", "/api/brains/one")
    assert brainsync.urllib.request.urlopen.call_args.args[0].full_url.startswith("http://old"), (
        "later requests go to the address that answered"
    )


def test_connect_says_how_to_switch_the_api_on(mocker):
    mocker.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused"))
    with pytest.raises(BrainError, match="Local API"):
        brainsync.connect(("http://new", "http://old"), "k")


class LocalApi(http.server.BaseHTTPRequestHandler):
    requests = []

    def answer(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length)) if length else None
        self.requests.append((self.command, self.path, body, self.headers.get("Authorization")))
        payload = json.dumps(self.reply()).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def reply(self):
        if self.path == "/api/brains":
            return [{"id": BRAIN, "name": "Mine", "homeThoughtId": HOME}]
        if self.path == f"/api/brains/{BRAIN}":
            return {"id": BRAIN, "name": "Mine", "homeThoughtId": HOME}
        return {"id": f"id-{len(self.requests)}"}

    do_GET = do_POST = do_PATCH = do_DELETE = answer

    def log_message(self, *_):
        pass


@pytest.fixture
def local_api():
    LocalApi.requests = []
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), LocalApi)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/api/"
    server.shutdown()
    server.server_close()


def writes(requests):
    return [r for r in requests if r[0] != "GET"]


def test_run_mirrors_over_real_http_and_then_has_nothing_left_to_do(tmp_path, local_api):
    folder = str(tmp_path)
    first = brainsync.run(PLAN, folder, "secret", url=local_api)
    sent = len(writes(LocalApi.requests))
    second = brainsync.run(PLAN, folder, "secret", url=local_api)
    assert (first.created, first.linked) == (6, 6), "the first run should build the whole mirror"
    assert {r[3] for r in LocalApi.requests} == {"Bearer secret"}, "every request carries the key"
    assert second == Report(0, 0, 0, 0, 0, 0), "the second run should find it all in .brain.json"
    assert len(writes(LocalApi.requests)) == sent, "and write nothing to TheBrain"


def test_run_saves_what_it_did_even_when_it_fails_halfway(tmp_path, local_api, mocker):
    mocker.patch.object(Remote, "link", side_effect=BrainError("no"))
    with pytest.raises(BrainError):
        brainsync.run(PLAN, str(tmp_path), "secret", url=local_api)
    saved = brainsync.load_state(str(tmp_path / ".brain.json"), BRAIN)
    assert len(saved["thoughts"]) == 6, "the created thoughts should be on file for the next run"
