import json
import os
import sys

from mash import query as queries
from mash.search import search
from mash.tree import Tree

DEFAULT_FOLDER = "~/.mash"


def folder():
    return os.path.expanduser(os.environ.get("MASH_FOLDER", DEFAULT_FOLDER))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "--alfred":
        return alfred(" ".join(argv[1:]))
    if argv and argv[0] == "-l":
        return listing(" ".join(argv[1:]))
    if argv and argv[0] == "add":
        return add(" ".join(argv[1:]))
    return best(" ".join(argv))


def hits_for(text):
    query = queries.parse(text)
    return query, search(Tree(folder()).load(), query)


def best(text):
    _, hits = hits_for(text)
    if not hits:
        return 1
    print(hits[0].stored.record.body)
    return 0


def listing(text):
    _, hits = hits_for(text)
    for hit in hits:
        record = hit.stored.record
        first_line = (record.query if record.is_rule else record.body).split("\n")[0]
        print(
            f"{hit.score:>3}  {hit.stored.node or '.'}  {record.head}  {record.arrow} {first_line}"
        )
    return 0 if hits else 1


def add(text):
    query = queries.parse(text)
    record = query.add or queries.records.from_box(text)
    path = Tree(folder()).add(query.node, record)
    print(f"Added to {query.node or '.'}: {record.head}  ({path})")
    return 0


def alfred(text):
    query, hits = hits_for(text)
    items = [alfred_item(hit) for hit in hits[:50]]
    items.append(add_item(query, text))
    json.dump({"items": items}, sys.stdout)
    return 0


def alfred_item(hit):
    record = hit.stored.record
    subtitle = f"{record.arrow} {record.query}" if record.is_rule else record.body.split("\n")[0]
    return {"title": record.head, "subtitle": subtitle, "arg": record.body}


def add_item(query, text):
    where = f"Add to {query.node}/" if query.node else "Add"
    return {"title": f"{where}: {text}", "arg": text}


if __name__ == "__main__":
    sys.exit(main())
