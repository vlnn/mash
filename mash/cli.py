import json
import os
import sys

from mash import actions, alfred, fill, search
from mash import query as queries
from mash.journal import Journal
from mash.session import Session, Settings, query_text_without_node, read_clipboard
from mash.tree import Tree

DEFAULT_FOLDER = "~/.mash"
JOURNAL = ".journal.log"
NO_BRAIN_KEY = "Set MASH_BRAIN_KEY to TheBrain's local API key (Settings > User > Local API)"
MANUAL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "help")

USAGE = """mash — fuzzy search over a tree of plain-text records

  mash WORDS              print the resolved body of the best hit
  mash -l [WORDS]         list every hit: score, node, head, first line
  mash help/ WORDS        search the manual that ships with mash
  mash add 'HEAD -> BODY' store a record (node/ first to choose the node)
  mash fill BODY k=v ...  fill {{blanks}} in a body
  mash forget WORDS       remove the best-matching record and its history
  mash forget --node N/   remove a node and everything under it
  mash forget --journal WORDS   keep the record, drop its history
  mash brain [--facts] [--manual]   show the tree as TheBrain would get it; nothing is sent
  mash brain sync [--facts] [--manual] [--prune]   mirror the tree into TheBrain
  mash --alfred TEXT      Script Filter JSON
  mash --act JSON         perform a row's command, print the notification
  mash --prompt JSON TYPED  rows for filling a blank

Folder: $MASH_FOLDER or ~/.mash. Exit 0 on a hit, 1 on none.
TheBrain: $MASH_BRAIN_KEY, and $MASH_BRAIN_ID when there are several brains."""


def folder():
    return os.path.expanduser(
        os.environ.get("MASH_FOLDER") or os.environ.get("folder") or DEFAULT_FOLDER
    )


def setting(name, default):
    return os.environ.get(f"MASH_{name.upper()}") or os.environ.get(name) or default


def settings():
    return Settings(
        editor=setting("editor", "open -t {file}"),
        flows=actions.parse_flows(setting("flows", "")),
        max_results=int(setting("max_results", "50")),
    )


def session():
    tree = Tree(folder(), mounts={"help": MANUAL})
    return Session(tree, Journal(os.path.join(folder(), JOURNAL)), settings())


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


def find(current, snapshot, argv):
    query = queries.parse(" ".join(argv))
    return search.search(snapshot.records, query, current.journal.touched())


def best(argv):
    current = session()
    snapshot = current.tree.load()
    hits = find(current, snapshot, argv)
    if not hits:
        return 1
    chain = current.resolve_chain(snapshot, hits[0].stored)
    if chain.fact is None:
        print(chain.error, file=sys.stderr)
        return 1
    current.touch_chain(chain.chain, "print")
    print(fill.preview(chain.fact.record.body))
    return 0


@command("-l")
def listing(argv):
    current = session()
    hits = find(current, current.tree.load(), argv)
    for hit in hits:
        record = hit.stored.record
        first = (f"{record.arrow} {record.query}" if record.is_rule else record.body).split("\n")[0]
        print(f"{hit.score:>3}  {hit.stored.node or '.':<12}  {record.head}  ·  {first}")
    return 0 if hits else 1


@command("add")
def add(argv):
    query = queries.parse(" ".join(argv))
    text = query_text_without_node(" ".join(argv), query.node)
    print(session().add(query.node, text))
    return 0


@command("fill")
def fill_command(argv):
    body, pairs = argv[0], argv[1:]
    values = dict(pair.partition("=")[::2] for pair in pairs if "=" in pair)
    print(fill.fill(body, values, read_clipboard))
    return 0


@command("forget")
def forget(argv):
    current = session()
    if argv[:1] == ["--node"]:
        return forget_node(current, argv[1].rstrip("/"))
    history_only = argv[:1] == ["--journal"]
    words = argv[1:] if history_only else argv
    hits = find(current, current.tree.load(), words)
    if not hits:
        print("nothing matches", file=sys.stderr)
        return 1
    stored = hits[0].stored
    if stored.shipped and not history_only:
        print(current.delete(stored), file=sys.stderr)
        return 1
    what = "history of" if history_only else "record"
    if not confirm(f"forget {what} {stored.record.head!r} in {stored.node or '.'} ({stored.path})"):
        return 1
    print(current.forget_history(stored) if history_only else current.delete(stored))
    return 0


def forget_node(current, node):
    if not current.owns_node(node):
        print(f"no node {node}/", file=sys.stderr)
        return 1
    size, path = current.node_size(node), current.tree.own_folder(node)
    if not confirm(f"remove {node}/ with {size} records ({path})"):
        return 1
    print(current.forget_node(node))
    return 0


@command("brain")
def brain_command(argv):
    from mash import brain

    uses = Journal(os.path.join(folder(), JOURNAL)).uses()
    plan = brain.plan(brain_tree("--manual" in argv).load(), uses, facts="--facts" in argv)
    if "sync" in argv:
        return brain_sync(plan, prune="--prune" in argv)
    print("\n".join(brain.outline(plan)))
    return 0


def brain_tree(with_manual):
    return session().tree if with_manual else Tree(folder())


def brain_sync(plan, prune):
    from mash import brainsync

    key = setting("brain_key", "")
    if not key:
        print(NO_BRAIN_KEY, file=sys.stderr)
        return 1
    where = setting("brain_id", ""), setting("brain_url", "")
    try:
        report = brainsync.run(plan, folder(), key, *where, prune)
    except brainsync.BrainError as error:
        print(error, file=sys.stderr)
        return 1
    print(brainsync.summary(report))
    return 0


def confirm(what):
    print(f"About to {what}. Continue? [y/N] ", end="", flush=True)
    return sys.stdin.readline().strip().lower() == "y"


@command("--alfred")
def alfred_items(argv):
    json.dump(alfred.items(session(), " ".join(argv)), sys.stdout, ensure_ascii=False)
    return 0


@command("--act")
def alfred_act(argv):
    message = alfred.act(session(), json.loads(argv[0]))
    if message:
        print(message)
    return 0


@command("--prompt")
def alfred_prompt(argv):
    typed = " ".join(argv[1:]).strip()
    json.dump(alfred.prompt(session(), json.loads(argv[0]), typed), sys.stdout, ensure_ascii=False)
    return 0


@command("--resolve")
def resolve_command(argv):
    current = session()
    snapshot = current.tree.load()
    hits = find(current, snapshot, argv)
    if not hits:
        return 1
    chain = current.resolve_chain(snapshot, hits[0].stored)
    print(" → ".join(s.record.head for s in chain.chain), chain.error or "", sep="  ")
    return 0 if chain.fact else 1


def run():
    sys.exit(main())


if __name__ == "__main__":
    run()
