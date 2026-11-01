import json
import os
from typing import NamedTuple

from mash import actions, fill, resolve, search, tree
from mash import query as queries
from mash import records as record_grammar

NODE_ICON = {"path": "node.png"}


class Settings(NamedTuple):
    editor: str = "open -t {file}"
    flows: dict = {}
    max_results: int = 50


def read_clipboard():
    import subprocess

    return subprocess.run(["pbpaste"], capture_output=True, check=False).stdout.decode("utf-8")


class Session:
    def __init__(self, tree, journal, settings):
        self.tree = tree
        self.journal = journal
        self.settings = settings

    def items(self, text):
        query = queries.parse(search_text(text))
        stored = self.tree.load()
        hits = search.search(stored, query, self.journal.touched())
        self.nodes = tree.node_counts(stored)
        rows = self.node_rows(query, text) + [
            self.row(hit) for hit in hits[: self.settings.max_results]
        ]
        if query.add:
            rows.insert(0, self.add_row(query, text))
        else:
            if hits and usable(text):
                rows.append(run_row(text))
            rows.append(self.add_row(query, text))
        return {"items": rows, "variables": {"prompt": "0"}}

    def node_rows(self, query, text):
        if query.add or query.tags or len(query.words) > 1:
            return []
        if not query.words:
            children = self.tree.children(query.node)
            return [node_row(child, self.nodes.get(child, 0)) for child in children]
        if query.node:
            return []
        prefix = query.words[0].lower()
        return [
            node_row(node, count)
            for node, count in sorted(self.nodes.items())
            if node.split("/")[-1].lower().startswith(prefix)
        ]

    def row(self, hit):
        record = hit.stored.record
        path = hit.stored.path
        command = self.command_for(hit.stored)
        return {
            "title": record.head,
            "subtitle": self.subtitle(record),
            "arg": dumps(command),
            "variables": {"prompt": "1" if command["do"] == "prompt" else "0"},
            "mods": {
                "shift": {"arg": dumps(dict(command, mode="paste")), "subtitle": "Paste"},
                "cmd": {"arg": dumps(act(path, "edit")), "subtitle": f"Edit {path}"},
                "alt": {"arg": dumps(act(path, "delete")), "subtitle": "Delete this record"},
                "ctrl": {"arg": dumps(command), "subtitle": self.detail(hit.stored)},
            },
            "text": {"copy": record.body, "largetype": record.body},
        }

    def command_for(self, stored):
        record = stored.record
        if not record.is_rule and fill.blanks(record.body):
            return dict(act(stored.path, "copy"), do="prompt", values={})
        return act(stored.path, "copy")

    def subtitle(self, record):
        if record.is_rule:
            return f"{record.arrow} {record.query}"
        first_line = fill.preview(record.body).split("\n")[0]
        action = actions.decide(first_line, os.path.exists, self.settings.flows)
        if action.kind == "open":
            return f"Open · {first_line}"
        if action.kind == "handoff":
            keyword, _, rest = action.target.partition(" ")
            return f"→ {keyword} · {rest}".rstrip(" ·")
        return first_line

    def detail(self, stored):
        return f"{stored.path} · {self.subtitle(stored.record)}"

    def add_row(self, query, text):
        node = query.node
        where = f"Add to {node}/" if node else "Add"
        if node and node not in self.nodes:
            where += " (new node)"
        shown = query_text_without_node(text, node)
        record = query.add or record_grammar.from_box(shown)
        return {
            "title": f"{where}: {shown}",
            "subtitle": fill.preview(record.body)
            if not record.is_rule
            else f"rule {record.arrow} {record.query}",
            "arg": dumps({"do": "add", "node": node, "text": shown}),
            "icon": {"path": "add.png"},
        }

    def act(self, command):
        do = command["do"]
        if do == "add":
            return self.add(command["node"], command["text"])
        if do == "run":
            return self.run_text(command["text"], command.get("mode", "copy"))
        stored = self.tree.read(command["path"])
        mode = command.get("mode", "copy")
        if mode == "edit":
            return self.edit(stored)
        if mode == "delete":
            return self.delete(stored)
        return self.use(stored, mode, command.get("values", {}))

    def use(self, stored, mode, values):
        chain = self.resolve_chain(stored)
        if chain.fact is None:
            return f"Could not resolve: {chain.error}"
        body = fill.fill(chain.fact.record.body, values, read_clipboard)
        if fill.blanks(body):
            return "Fill in the blanks first"
        for step in chain.chain:
            self.journal.touch(step.identity, mode, step.node)
        message = self.do(body, mode)
        if len(chain.chain) > 1:
            return " → ".join([s.record.head for s in chain.chain] + [body.split("\n")[0]])
        return message

    def resolve_chain(self, stored):
        return resolve.resolve(self.tree.load(), stored, self.journal.touched())

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
        try:
            self.tree.delete(stored)
        except LookupError as error:
            return str(error)
        self.journal.forget(stored.identity)
        return f"Deleted: {stored.record.head}"

    def prompt(self, command, typed):
        stored = self.tree.read(command["path"])
        values = command.get("values", {})
        pending = [(n, d) for n, d in fill.blanks(stored.record.body) if n not in values]
        name, default = pending[0]
        total = len(fill.blanks(stored.record.body))
        position = total - len(pending) + 1
        choices = [c for c in (typed, default, read_clipboard().strip()) if c]
        rows = []
        for choice in dict.fromkeys(choices):
            chosen = dict(values, **{name: choice})
            remaining = pending[1:]
            next_command = dict(command, values=chosen, do="prompt" if remaining else "act")
            rows.append(
                {
                    "title": f"{name} ({position}/{total}): {choice}",
                    "subtitle": fill.fill(stored.record.body, chosen, lambda: "{{clipboard}}"),
                    "arg": dumps(next_command),
                    "variables": {"more": "1" if remaining else "0"},
                }
            )
        return {"items": rows}


def act(path, mode):
    return {"do": "act", "path": path, "mode": mode}


def node_row(node, count):
    plural = "record" if count == 1 else "records"
    return {
        "title": f"{node}/",
        "subtitle": f"{count} {plural} · ↩ to search inside",
        "autocomplete": f"{node}/ ",
        "valid": False,
        "icon": NODE_ICON,
    }


def run_row(text):
    return {
        "title": f"Run: {text}",
        "subtitle": "Act on this text without storing it",
        "arg": dumps({"do": "run", "text": text}),
        "mods": {"shift": {"arg": dumps({"do": "run", "text": text, "mode": "paste"})}},
    }


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


def dumps(command):
    return json.dumps(command, ensure_ascii=False)
