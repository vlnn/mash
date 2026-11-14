import os
from typing import NamedTuple, Optional

from mash import actions, fill, resolve, search
from mash import query as queries
from mash import records as record_grammar


class Settings(NamedTuple):
    editor: str = "open -t {file}"
    flows: dict = {}
    max_results: int = 50


class Add(NamedTuple):
    node: str
    new: bool
    text: str
    record: record_grammar.Record


class Listing(NamedTuple):
    query: queries.Query
    folders: list
    hits: list
    run: Optional[str]
    add: Add


class Option(NamedTuple):
    value: str
    values: dict
    preview: str
    more: bool


class Prompt(NamedTuple):
    name: str
    position: int
    total: int
    options: list


def read_clipboard():
    import subprocess

    return subprocess.run(["pbpaste"], capture_output=True, check=False).stdout.decode("utf-8")


class Session:
    def __init__(self, tree, journal, settings):
        self.tree = tree
        self.journal = journal
        self.settings = settings

    def listing(self, text):
        query = queries.parse(search_text(text))
        snapshot = self.tree.load()
        hits = search.search(snapshot.records, query, self.journal.touched())
        run = text if hits and not query.add and usable(text) else None
        return Listing(
            query,
            folders(query, snapshot),
            hits[: self.settings.max_results],
            run,
            add_offer(query, text, snapshot),
        )

    def resolve_chain(self, snapshot, stored):
        return resolve.resolve(snapshot.records, stored, self.journal.touched())

    def touch_chain(self, chain, action):
        for step in chain:
            self.journal.touch(step.identity, action, step.node)

    def use(self, stored, mode, values):
        chain = self.resolve_chain(self.tree.load(), stored)
        if chain.fact is None:
            return f"Could not resolve: {chain.error}"
        body = fill.fill(chain.fact.record.body, values, read_clipboard)
        if fill.blanks(body):
            return "Fill in the blanks first"
        self.touch_chain(chain.chain, mode)
        message = self.do(body, mode)
        if len(chain.chain) > 1:
            return " → ".join([s.record.head for s in chain.chain] + [body.split("\n")[0]])
        return message

    def do(self, body, mode):
        action = actions.decide(body, os.path.exists, self.settings.flows)
        actions.perform(action)
        if mode == "paste" and action.kind == "copy":
            actions.paste()
            return f"Pasted: {body}"
        return {"open": "Opened: ", "handoff": "Alfred: ", "copy": "Copied: "}[
            action.kind
        ] + action.target

    def run_text(self, text, mode):
        return self.do(fill.fill(text, {}, read_clipboard), mode)

    def add(self, node, text):
        record = record_grammar.from_box(text)
        twin = twin_of(self.tree.load().records, node, record)
        if twin:
            self.journal.touch(twin.identity, "add", node)
            return f"Already there: {record.head}"
        path = self.tree.add(node, record)
        self.journal.touch(self.tree.read(path).identity, "add", node)
        return f"Added to {node + '/' if node else '.'}: {record.head}"

    def edit(self, stored):
        import shlex
        import subprocess

        command = [
            part.replace("{file}", stored.path) for part in shlex.split(self.settings.editor)
        ]
        subprocess.run(command, check=False)
        return f"Editing {stored.path}"

    def delete(self, stored):
        if stored.shipped:
            return f"Not deleted: {stored.record.head} is part of mash's manual"
        try:
            self.tree.delete(stored)
        except LookupError as error:
            return str(error)
        self.journal.forget(stored.identity)
        return f"Deleted: {stored.record.head}"

    def forget_history(self, stored):
        self.journal.forget(stored.identity)
        return f"Forgot history of: {stored.record.head}"

    def prompt(self, stored, values, typed):
        body = stored.record.body
        pending = [(n, d) for n, d in fill.blanks(body) if n not in values]
        name, default = pending[0]
        total = len(fill.blanks(body))
        more = len(pending) > 1
        options = [
            option(body, values, name, choice, more)
            for choice in dict.fromkeys(c for c in (typed, default, read_clipboard().strip()) if c)
        ]
        return Prompt(name, total - len(pending) + 1, total, options)


def twin_of(stored_records, node, record):
    return next((s for s in stored_records if s.node == node and s.record == record), None)


def option(body, values, name, choice, more):
    chosen = dict(values, **{name: choice})
    return Option(choice, chosen, fill.fill(body, chosen, lambda: "{{clipboard}}"), more)


def folders(query, snapshot):
    if query.add or query.tags or len(query.words) > 1:
        return []
    if not query.words:
        nodes = snapshot.children(query.node)
    elif query.node:
        nodes = []
    else:
        nodes = snapshot.named_like(query.words[0])
    return [(node, snapshot.folders[node]) for node in nodes]


def add_offer(query, text, snapshot):
    node = query.node
    shown = query_text_without_node(text, node)
    record = query.add or record_grammar.from_box(shown)
    return Add(node, bool(node) and node not in snapshot.folders, shown, record)


def usable(text):
    action = actions.decide(text, os.path.exists, {})
    return action.kind != "copy" or bool(fill.blanks(text)) or "{{" in text


def search_text(text):
    handoff = actions.handoff_of(text.strip(), {})
    if handoff is None or records_arrow(text):
        return text
    return handoff.partition(" ")[2]


def records_arrow(text):
    return record_grammar.ARROW.search(text) is not None


def query_text_without_node(text, node):
    if not node:
        return text.strip()
    return " ".join(t for t in text.split() if not queries.is_node(t)).strip()
