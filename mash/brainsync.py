import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import NamedTuple

from mash import brain
from mash.tree import write_atomically

STATE = ".brain.json"
DEFAULT_URLS = ("http://localhost:11522", "http://localhost:8001")
HOME_KEY = "home"
HOME_LINK = brain.Link(HOME_KEY, brain.ROOT_KEY, brain.CHILD)
KINDS = {brain.THOUGHT: 1, brain.TYPE: 2, brain.TAG: 4}
RELATIONS = {brain.CHILD: 1, brain.TAGGED: 2, brain.JUMP: 3}
ZERO_ID = "00000000-0000-0000-0000-000000000000"
JSON, JSON_PATCH = "application/json", "application/json-patch+json"
TIMEOUT = 30
NOT_ANSWERING = (
    "TheBrain is not answering at {urls}. "
    "Is the desktop app open, with Settings > User > Local API switched on?"
)


class BrainError(Exception):
    pass


class Unreachable(BrainError):
    pass


class Report(NamedTuple):
    created: int
    updated: int
    removed: int
    linked: int
    unlinked: int
    stale: int


class Remote:
    def __init__(self, send, brain_id):
        self.send = send
        self.brain_id = brain_id

    def home(self):
        return self.send("GET", f"/api/brains/{self.brain_id}")["homeThoughtId"]

    def create(self, thought, type_id):
        body = {"name": thought.name, "kind": KINDS[thought.kind], "acType": 0}
        if thought.label:
            body["label"] = thought.label
        if type_id:
            body["typeId"] = type_id
        return self.send("POST", f"/api/thoughts/{self.brain_id}", body)["id"]

    def retitle(self, thought_id, thought):
        label = (
            {"op": "replace", "path": "/label", "value": thought.label}
            if thought.label
            else {"op": "remove", "path": "/label"}
        )
        patch = [{"op": "replace", "path": "/name", "value": thought.name}, label]
        self.send("PATCH", f"/api/thoughts/{self.brain_id}/{thought_id}", patch)

    def write_note(self, thought_id, markdown):
        self.send("POST", f"/api/notes/{self.brain_id}/{thought_id}/update", {"markdown": markdown})

    def attach(self, thought_id, url, name):
        path = f"/api/attachments/{self.brain_id}/{thought_id}/url"
        self.send("POST", path, None, {"url": url, "name": name})

    def link(self, source_id, target_id, link):
        body = {
            "thoughtIdA": source_id,
            "thoughtIdB": target_id,
            "relation": RELATIONS[link.relation],
        }
        if link.name:
            body["name"] = link.name
        made = self.send("POST", f"/api/links/{self.brain_id}", body)["id"]
        if made == ZERO_ID:
            raise BrainError(f"TheBrain did not make the link {link.source} → {link.target}")
        return made

    def unlink(self, link_id):
        self.send("DELETE", f"/api/links/{self.brain_id}/{link_id}")

    def delete(self, thought_id):
        self.send("DELETE", f"/api/thoughts/{self.brain_id}/{thought_id}")


def sync(plan, state, remote, prune=False):
    planned = keys_of(plan)
    stale = [key for key in state["thoughts"] if key not in planned]
    removed = forget_thoughts(stale, state, remote) if prune else 0
    created, updated = push_thoughts(plan.thoughts, state, remote)
    wanted = wanted_links(plan)
    unlinked = drop_links(wanted, planned, state, remote)
    linked = make_links(wanted, state, remote)
    return Report(created, updated, removed, linked, unlinked, len(stale) - removed)


def keys_of(plan):
    return {thought.key for thought in plan.thoughts}


def forget_thoughts(keys, state, remote):
    done = set()
    try:
        for key in keys:
            remote.delete(state["thoughts"][key]["id"])
            del state["thoughts"][key]
            done.add(key)
    finally:
        state["links"] = [known for known in state["links"] if done.isdisjoint(ends(known))]
    return len(keys)


def push_thoughts(thoughts, state, remote):
    created = updated = 0
    for thought in sorted(thoughts, key=lambda t: t.kind != brain.TYPE):
        if thought.key not in state["thoughts"]:
            create_thought(thought, state, remote)
            created += 1
        elif update_thought(thought, state["thoughts"][thought.key], remote):
            updated += 1
    return created, updated


def create_thought(thought, state, remote):
    type_id = state["thoughts"][thought.type]["id"] if thought.type else ""
    known = {"id": remote.create(thought, type_id), "name": thought.name, "label": thought.label}
    state["thoughts"][thought.key] = known
    update_thought(thought, known, remote)


def update_thought(thought, known, remote):
    changes = [
        retitled(thought, known, remote),
        renoted(thought, known, remote),
        reattached(thought, known, remote),
    ]
    return any(changes)


def retitled(thought, known, remote):
    if (known["name"], known["label"]) == (thought.name, thought.label):
        return False
    remote.retitle(known["id"], thought)
    known.update(name=thought.name, label=thought.label)
    return True


def renoted(thought, known, remote):
    if known.get("note", "") == thought.note:
        return False
    remote.write_note(known["id"], thought.note)
    known["note"] = thought.note
    return True


def reattached(thought, known, remote):
    if not thought.url or known.get("url", "") == thought.url:
        return False
    remote.attach(known["id"], thought.url, thought.name)
    known["url"] = thought.url
    return True


def wanted_links(plan):
    rooted = [HOME_LINK] * (brain.ROOT_KEY in keys_of(plan))
    return [*rooted, *plan.links]


def as_link(known):
    return brain.Link(known["source"], known["target"], known["relation"], known["name"])


def ends(known):
    return (known["source"], known["target"])


def drop_links(wanted, planned, state, remote):
    wanted = set(wanted)
    doomed = [
        known
        for known in state["links"]
        if as_link(known) not in wanted and not outlives_the_plan(known, planned)
    ]
    done = set()
    try:
        for known in doomed:
            remote.unlink(known["id"])
            done.add(known["id"])
    finally:
        state["links"] = [known for known in state["links"] if known["id"] not in done]
    return len(doomed)


def outlives_the_plan(known, planned):
    return any(key != HOME_KEY and key not in planned for key in ends(known))


def make_links(wanted, state, remote):
    made = {as_link(known) for known in state["links"]}
    missing = [link for link in wanted if link not in made]
    for link in missing:
        source, target = (thought_id(key, state, remote) for key in (link.source, link.target))
        state["links"].append(dict(link._asdict(), id=remote.link(source, target, link)))
    return len(missing)


def thought_id(key, state, remote):
    return remote.home() if key == HOME_KEY else state["thoughts"][key]["id"]


def summary(report):
    counts = (
        f"TheBrain: {report.created} created, {report.updated} updated, {report.linked} linked, "
        f"{report.unlinked} unlinked, {report.removed} removed"
    )
    return counts + leftovers(report.stale)


def leftovers(stale):
    if not stale:
        return ""
    some, them = ("1 thought is", "it") if stale == 1 else (f"{stale} thoughts are", "them")
    return f"\n{some} no longer in mash; mash brain sync --prune deletes {them}"


def new_state(brain_id):
    return {"brain": brain_id, "thoughts": {}, "links": []}


def load_state(path, brain_id):
    if not os.path.exists(path):
        return new_state(brain_id)
    with open(path, encoding="utf-8") as f:
        state = json.load(f)
    if state["brain"] != brain_id:
        raise BrainError(
            f"{path} remembers another brain ({state['brain']}). "
            "Sync to that one, or delete the file to start over in this one."
        )
    return state


def save_state(path, state):
    write_atomically(path, json.dumps(state, ensure_ascii=False, indent=1))


def pick_brain(brains, wanted):
    if wanted:
        return wanted
    if len(brains) == 1:
        return brains[0]["id"]
    if not brains:
        raise BrainError("TheBrain lists no brains")
    listed = "\n".join(f"{b['id']}  {b.get('name') or ''}" for b in brains)
    raise BrainError(f"Several brains; set MASH_BRAIN_ID to one of:\n{listed}")


def connect(urls, key):
    for url in urls:
        send = http(url, key)
        try:
            return send, send("GET", "/api/brains")
        except Unreachable:
            continue
    raise BrainError(NOT_ANSWERING.format(urls=" or ".join(urls)))


def http(base, key):
    base = base_of(base)

    def send(method, path, body=None, query=None):
        request = urllib.request.Request(
            base + path + query_string(query),
            data=None if body is None else json.dumps(body).encode("utf-8"),
            headers=headers(key, method, body),
            method=method,
        )
        return parsed(answer(request, method, path), method, path)

    return send


def base_of(url):
    stripped = url.strip().rstrip("/")
    return stripped[: -len("/api")] if stripped.endswith("/api") else stripped


def query_string(query):
    return "?" + urllib.parse.urlencode(query) if query else ""


def headers(key, method, body):
    fixed = {"Authorization": f"Bearer {key}", "Accept": JSON}
    if body is None:
        return fixed
    return dict(fixed, **{"Content-Type": JSON_PATCH if method == "PATCH" else JSON})


def answer(request, method, path):
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as refusal:
        detail = refusal.read().decode("utf-8", errors="replace").strip()[:300]
        raise BrainError(f"{method} {path}: {refusal.code} {detail}") from refusal
    except (urllib.error.URLError, OSError) as failure:
        raise Unreachable(NOT_ANSWERING.format(urls=request.full_url)) from failure


def parsed(text, method, path):
    if not text.strip():
        return None
    if text.lstrip().startswith("<"):
        raise BrainError(f"{method} {path}: TheBrain answered with a page, not data")
    try:
        return json.loads(text)
    except ValueError:
        return text


def run(plan, folder, key, brain_id="", url="", prune=False):
    send, brains = connect((url,) if url else DEFAULT_URLS, key)
    chosen = pick_brain(brains, brain_id)
    path = os.path.join(folder, STATE)
    state = load_state(path, chosen)
    try:
        return sync(plan, state, Remote(send, chosen), prune)
    finally:
        save_state(path, state)
