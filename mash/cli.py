import json
import os
import shutil
import sys

from mash import actions, alfred, fill, resolve, search
from mash import query as queries
from mash.journal import Journal
from mash.tree import Tree

DEFAULT_FOLDER = "~/.mash"
JOURNAL = ".journal.log"

USAGE = """mash — fuzzy search over a tree of plain-text records

  mash WORDS              print the resolved body of the best hit
  mash -l [WORDS]         list every hit: score, node, head, first line
  mash add 'HEAD -> BODY' store a record (node/ first to choose the node)
  mash fill BODY k=v ...  fill {{blanks}} in a body
  mash forget WORDS       remove the best-matching record and its history
  mash forget --node N/   remove a node and everything under it
  mash forget --journal WORDS   keep the record, drop its history
  mash --alfred TEXT      Script Filter JSON
  mash --act JSON         perform a row's command, print the notification
  mash --prompt JSON TYPED  rows for filling a blank

Folder: $MASH_FOLDER or ~/.mash. Exit 0 on a hit, 1 on none."""


def folder():
    return os.path.expanduser(
        os.environ.get("MASH_FOLDER") or os.environ.get("folder") or DEFAULT_FOLDER
    )


def setting(name, default):
    return os.environ.get(f"MASH_{name.upper()}") or os.environ.get(name) or default


def settings():
    return alfred.Settings(
        editor=setting("editor", "open -t {file}"),
        flows=actions.parse_flows(setting("flows", "")),
        max_results=int(setting("max_results", "50")),
        show_nodes=setting("show_nodes", "") in ("1", "true", "yes"),
    )


def session():
    return alfred.Session(Tree(folder()), Journal(os.path.join(folder(), JOURNAL)), settings())


COMMANDS = {}


def command(name):
    def register(function):
        COMMANDS[name] = function
        return function

    return register


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        return listing([])
    if argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0
    if argv[0] in COMMANDS:
        return COMMANDS[argv[0]](argv[1:])
    return best(argv)


def find(current, argv):
    query = queries.parse(" ".join(argv))
    return search.search(current.tree.load(), query, current.journal.touched())


def best(argv):
    current = session()
    hits = find(current, argv)
    if not hits:
        return 1
    chain = current.resolve_chain(hits[0].stored)
    if chain.fact is None:
        print(chain.error, file=sys.stderr)
        return 1
    for step in chain.chain:
        current.journal.touch(step.node, step.record.head, "print")
    print(chain.fact.record.body)
    return 0


@command("-l")
def listing(argv):
    current = session()
    hits = find(current, argv)
    for hit in hits:
        record = hit.stored.record
        first = (f"{record.arrow} {record.query}" if record.is_rule else record.body).split("\n")[0]
        print(f"{hit.score:>3}  {hit.stored.node or '.':<12}  {record.head}  ·  {first}")
    return 0 if hits else 1


@command("add")
def add(argv):
    query = queries.parse(" ".join(argv))
    text = alfred.query_text_without_node(" ".join(argv), query.node)
    print(session().act({"do": "add", "node": query.node, "text": text}))
    return 0


@command("fill")
def fill_command(argv):
    body, pairs = argv[0], argv[1:]
    values = dict(pair.partition("=")[::2] for pair in pairs if "=" in pair)
    print(fill.fill(body, values, alfred.read_clipboard))
    return 0


@command("forget")
def forget(argv):
    current = session()
    if argv[:1] == ["--node"]:
        return forget_node(current, argv[1].rstrip("/"))
    history_only = argv[:1] == ["--journal"]
    words = argv[1:] if history_only else argv
    hits = find(current, words)
    if not hits:
        print("nothing matches", file=sys.stderr)
        return 1
    stored = hits[0].stored
    what = "history of" if history_only else "record"
    if not confirm(f"forget {what} {stored.record.head!r} in {stored.node or '.'} ({stored.path})"):
        return 1
    if history_only:
        current.journal.forget(stored.node, stored.record.head)
        print(f"Forgot history of: {stored.record.head}")
    else:
        print(current.delete(stored))
    return 0


def forget_node(current, node):
    path = os.path.join(current.tree.root, *node.split("/"))
    if not os.path.isdir(path):
        print(f"no node {node}/", file=sys.stderr)
        return 1
    count = current.tree.nodes().get(node, 0)
    if not confirm(f"remove {node}/ with {count} records ({path})"):
        return 1
    shutil.rmtree(path)
    current.journal.forget_node(node)
    print(f"Removed node: {node}/")
    return 0


def confirm(what):
    print(f"About to {what}. Continue? [y/N] ", end="", flush=True)
    return sys.stdin.readline().strip().lower() == "y"


@command("--alfred")
def alfred_items(argv):
    json.dump(session().items(" ".join(argv)), sys.stdout, ensure_ascii=False)
    return 0


@command("--act")
def alfred_act(argv):
    print(session().act(json.loads(argv[0])))
    return 0


@command("--prompt")
def alfred_prompt(argv):
    typed = " ".join(argv[1:]).strip()
    json.dump(session().prompt(json.loads(argv[0]), typed), sys.stdout, ensure_ascii=False)
    return 0


@command("--resolve")
def resolve_command(argv):
    current = session()
    hits = find(current, argv)
    if not hits:
        return 1
    chain = resolve.resolve(current.tree.load(), hits[0].stored, current.journal.touched())
    print(" → ".join(s.record.head for s in chain.chain), chain.error or "", sep="  ")
    return 0 if chain.fact else 1


def run():
    sys.exit(main())


if __name__ == "__main__":
    run()
