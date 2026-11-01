import os
import re
import subprocess
from typing import NamedTuple

URL = re.compile(r"^(https?|file)://\S+$")
LEADING_HANDOFF = re.compile(r"^@(\S+)(?:\s+(.*))?$", re.DOTALL)
TRAILING_HANDOFF = re.compile(r"^(.*?)\s+@(\S+)$", re.DOTALL)
ALFRED = "com.runningwithcrayons.Alfred"


class Action(NamedTuple):
    kind: str
    target: str


def decide(body, exists, flows):
    if URL.match(body):
        return Action("open", body)
    handoff = handoff_of(body, flows)
    if handoff:
        return Action("handoff", handoff)
    path = os.path.expanduser(body)
    if looks_like_path(body) and exists(path):
        return Action("open", path)
    return Action("copy", body)


def looks_like_path(body):
    return "\n" not in body and body.startswith(("/", "~"))


def handoff_of(body, flows):
    match = LEADING_HANDOFF.match(body)
    if match:
        word, text = match.group(1), match.group(2) or ""
    else:
        match = TRAILING_HANDOFF.match(body)
        if not match:
            return None
        text, word = match.group(1), match.group(2)
    keyword = flows.get(word, word)
    return f"{keyword} {text}".strip()


def parse_flows(text):
    pairs = (part.partition("=") for part in text.split())
    return {name: keyword for name, eq, keyword in pairs if eq}


def perform(action):
    if action.kind == "copy":
        subprocess.run(["pbcopy"], input=action.target.encode("utf-8"), check=True)
    elif action.kind == "open":
        subprocess.run(["open", action.target], check=True)
    elif action.kind == "handoff":
        script = f'tell application id "{ALFRED}" to search "{escape(action.target)}"'
        subprocess.run(["osascript", "-e", script], check=True)


def paste():
    script = 'tell application "System Events" to keystroke "v" using command down'
    subprocess.run(["osascript", "-e", script], check=False)


def escape(text):
    return text.replace("\\", "\\\\").replace('"', '\\"')
