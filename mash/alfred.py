import json
import os

from mash import actions, fill

NODE_ICON = {"path": "node.png"}
ADD_ICON = {"path": "add.png"}


def items(session, text):
    listing = session.listing(text)
    rows = [node_row(node, count) for node, count in listing.folders]
    rows += [row(session, hit.stored) for hit in listing.hits]
    if listing.query.add:
        rows.insert(0, add_row(listing.add))
    else:
        if listing.run is not None:
            rows.append(run_row(listing.run))
        rows.append(add_row(listing.add))
    return {"items": rows, "variables": {"prompt": "0"}}


def act(session, command):
    do = command["do"]
    if do == "add":
        return session.add(command["node"], command["text"])
    if do == "run":
        return session.run_text(command["text"], command.get("mode", "copy"))
    stored = session.tree.read(command["path"])
    mode = command.get("mode", "copy")
    if mode == "edit":
        return session.edit(stored)
    if mode == "delete":
        return session.delete(stored)
    return session.use(stored, mode, command.get("values", {}))


def prompt(session, command, typed):
    stored = session.tree.read(command["path"])
    asked = session.prompt(stored, command.get("values", {}), typed)
    return {"items": [prompt_row(command, asked, option) for option in asked.options]}


def prompt_row(command, asked, option):
    next_command = dict(command, values=option.values, do="prompt" if option.more else "act")
    return {
        "title": f"{asked.name} ({asked.position}/{asked.total}): {option.value}",
        "subtitle": option.preview,
        "arg": dumps(next_command),
        "variables": {"more": "1" if option.more else "0"},
    }


def row(session, stored):
    record = stored.record
    path = stored.path
    command = command_for(stored)
    subtitle = describe(session, record)
    return {
        "title": record.head,
        "subtitle": subtitle,
        "arg": dumps(command),
        "variables": {"prompt": "1" if command["do"] == "prompt" else "0"},
        "mods": {
            "shift": {"arg": dumps(dict(command, mode="paste")), "subtitle": "Paste"},
            "cmd": {"arg": dumps(act_command(path, "edit")), "subtitle": f"Edit {path}"},
            "alt": delete_mod(stored),
            "ctrl": {"arg": dumps(command), "subtitle": f"{path} · {subtitle}"},
        },
        "text": {"copy": record.body, "largetype": record.body},
    }


def delete_mod(stored):
    if stored.shipped:
        return {"valid": False, "subtitle": "Part of mash's manual: cannot be deleted"}
    return {"arg": dumps(act_command(stored.path, "delete")), "subtitle": "Delete this record"}


def command_for(stored):
    record = stored.record
    if not record.is_rule and fill.blanks(record.body):
        return dict(act_command(stored.path, "copy"), do="prompt", values={})
    return act_command(stored.path, "copy")


def act_command(path, mode):
    return {"do": "act", "path": path, "mode": mode}


def describe(session, record):
    if record.is_rule:
        return f"{record.arrow} {record.query}"
    first_line = fill.preview(record.body).split("\n")[0]
    action = actions.decide(first_line, os.path.exists, session.settings.flows)
    if action.kind == "open":
        return f"Open · {first_line}"
    if action.kind == "handoff":
        keyword, _, rest = action.target.partition(" ")
        return f"→ {keyword} · {rest}".rstrip(" ·")
    return first_line


def node_row(node, count):
    plural = "record" if count == 1 else "records"
    return {
        "title": f"{node}/",
        "subtitle": f"{count} {plural} · ↩ to search inside",
        "autocomplete": f"{node}/ ",
        "valid": False,
        "icon": NODE_ICON,
    }


def add_row(add):
    where = f"Add to {add.node}/" if add.node else "Add"
    if add.new:
        where += " (new node)"
    record = add.record
    return {
        "title": f"{where}: {add.text}",
        "subtitle": fill.preview(record.body)
        if not record.is_rule
        else f"rule {record.arrow} {record.query}",
        "arg": dumps({"do": "add", "node": add.node, "text": add.text}),
        "icon": ADD_ICON,
    }


def run_row(text):
    return {
        "title": f"Run: {text}",
        "subtitle": "Act on this text without storing it",
        "arg": dumps({"do": "run", "text": text}),
        "mods": {"shift": {"arg": dumps({"do": "run", "text": text, "mode": "paste"})}},
    }


def dumps(command):
    return json.dumps(command, ensure_ascii=False)
