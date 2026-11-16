import time
from typing import NamedTuple

from mash import actions, resolve
from mash import query as queries
from mash.tree import parent_of

THOUGHT, TYPE, TAG = "thought", "type", "tag"
CHILD, JUMP, TAGGED = "child", "jump", "tagged"
NODE_TYPE, RULE_TYPE, FACT_TYPE = "type:node", "type:rule", "type:fact"
TYPE_NAMES = {NODE_TYPE: "mash node", RULE_TYPE: "mash rule", FACT_TYPE: "mash fact"}
ROOT_KEY = "node:"
ROOT_NAME = "mash"
LINE_LIMIT = 80
MORE = " …"
ARROW = " → "


class Thought(NamedTuple):
    key: str
    name: str
    kind: str = THOUGHT
    type: str = ""
    label: str = ""
    note: str = ""
    url: str = ""


class Link(NamedTuple):
    source: str
    target: str
    relation: str
    name: str = ""


class Plan(NamedTuple):
    thoughts: tuple
    links: tuple


class Mirror(NamedTuple):
    records: list
    folders: dict
    uses: dict
    last_use: dict
    resolutions: dict
    facts: bool

    @property
    def shown(self):
        return [s for s in self.records if self.shows(s)]

    def shows(self, stored):
        return self.facts or stored.record.is_rule

    def own(self, node):
        return [s for s in self.records if s.node == node]

    def size(self, node):
        return self.folders[node] if node else len(self.records)


def plan(snapshot, uses, facts=False):
    mirror = mirror_of(snapshot, uses, facts)
    links = distinct_pairs(tree_links(mirror) + tag_links(mirror) + jump_links(mirror))
    thoughts = (
        type_thoughts(facts) + tag_thoughts(links) + node_thoughts(mirror) + record_thoughts(mirror)
    )
    return Plan(tuple(thoughts), tuple(links))


def mirror_of(snapshot, uses, facts):
    records = sorted(snapshot.records, key=lambda s: (s.node, s.record.head.lower(), s.path))
    touched = {identity: use.last for identity, use in uses.items()}
    return Mirror(
        records,
        snapshot.folders,
        uses,
        last_uses(records, touched),
        resolutions(records, touched),
        facts,
    )


def resolutions(records, touched):
    rules = [stored for stored in records if stored.record.is_rule]
    return {rule.path: resolve.resolve(records, rule, touched) for rule in rules}


def last_uses(records, touched):
    latest = {}
    for stored in records:
        if stored.identity in touched:
            for node in lineage(stored.node):
                latest[node] = max(touched[stored.identity], latest.get(node, 0.0))
    return latest


def lineage(node):
    yield ""
    while node:
        yield node
        node = parent_of(node)


def node_key(node):
    return ROOT_KEY + node


def record_key(stored):
    return "record:" + stored.identity


def tag_key(tag):
    return "tag:" + tag.lower()


def type_thoughts(facts):
    used = [NODE_TYPE, RULE_TYPE] + [FACT_TYPE] * facts
    return [Thought(key, TYPE_NAMES[key], TYPE) for key in used]


def tag_thoughts(links):
    used = sorted({link.target for link in links if link.relation == TAGGED})
    return [Thought(key, key.partition(":")[2], TAG) for key in used]


def node_thoughts(mirror):
    return [node_thought(node, mirror) for node in nodes(mirror)]


def nodes(mirror):
    return ["", *sorted(mirror.folders)]


def node_thought(node, mirror):
    return Thought(
        node_key(node),
        node.rpartition("/")[2] or ROOT_NAME,
        type=NODE_TYPE,
        label=node_label(mirror.size(node), mirror.last_use.get(node)),
        note="" if mirror.facts else node_note(mirror.own(node)),
    )


def node_label(count, last):
    size = f"{count} record{'s' * (count != 1)}"
    return size if last is None else f"{size} · last used {day(last)}"


def node_note(own):
    return "\n".join(listing_line(stored.record) for stored in own)


def listing_line(record):
    title = f"- **{record.head}**"
    if record.is_rule:
        return f"{title} {code(search_of(record))}"
    if record.body == record.head:
        return title
    line, cut = first_line(record.body)
    return f"{title} → {code(line)}{MORE * cut}"


def record_thoughts(mirror):
    return [rule_thought(s, mirror) if s.record.is_rule else fact_thought(s) for s in mirror.shown]


def rule_thought(stored, mirror):
    record = stored.record
    return Thought(
        record_key(stored),
        record.head,
        type=RULE_TYPE,
        label=search_of(record),
        note=rule_note(stored, mirror),
    )


def rule_note(stored, mirror):
    written = code(f"{stored.record.head} {search_of(stored.record)}")
    return "\n\n".join([written, landing(stored, mirror), usage(mirror.uses.get(stored.identity))])


def landing(stored, mirror):
    resolution = mirror.resolutions[stored.path]
    if resolution.fact is None:
        return f"Resolves to nothing: {resolution.error}"
    return "Resolves now to: " + ARROW.join(steps(resolution))


def steps(resolution):
    heads = [step.record.head for step in resolution.chain]
    value = brief(resolution.fact.record.body)
    return heads if value == heads[-1] else [*heads, value]


def usage(use):
    if use is None:
        return "never used"
    return f"used {use.count} time{'s' * (use.count != 1)}, last on {day(use.last)}"


def fact_thought(stored):
    record = stored.record
    plain = record.body == record.head
    return Thought(
        record_key(stored),
        record.head,
        type=FACT_TYPE,
        label="" if plain else brief(record.body),
        note="" if plain else fenced(record.body),
        url=record.body if actions.URL.match(record.body) else "",
    )


def tree_links(mirror):
    folders = [Link(node_key(parent_of(n)), node_key(n), CHILD) for n in nodes(mirror) if n]
    records = [Link(node_key(s.node), record_key(s), CHILD) for s in mirror.shown]
    return folders + records


def tag_links(mirror):
    return [
        Link(carrier_key(stored, mirror), tag_key(tag), TAGGED)
        for stored in mirror.records
        for tag in tags_of(stored.record)
    ]


def carrier_key(stored, mirror):
    return record_key(stored) if mirror.shows(stored) else node_key(stored.node)


def tags_of(record):
    searched = queries.parse(record.query).tags if record.is_rule else ()
    return (*record.tags, *searched)


def jump_links(mirror):
    rules = [s for s in mirror.records if s.record.is_rule]
    aimed = [(rule, jump_target(rule, mirror)) for rule in rules]
    return [
        Link(record_key(rule), target, JUMP, rule.record.arrow)
        for rule, target in aimed
        if target and target != record_key(rule)
    ]


def jump_target(rule, mirror):
    query = queries.parse(rule.record.query)
    if query.node:
        return node_key(query.node) if query.node in mirror.folders else None
    if not query.words:
        return None
    chain = mirror.resolutions[rule.path].chain
    return carrier_key(chain[1], mirror) if len(chain) > 1 else None


def distinct_pairs(links):
    first = {}
    for link in links:
        first.setdefault(frozenset((link.source, link.target)), link)
    return list(first.values())


def search_of(record):
    return f"{record.arrow} {record.query}"


def first_line(body):
    line, _, rest = body.partition("\n")
    return line[:LINE_LIMIT], bool(rest) or len(line) > LINE_LIMIT


def brief(body):
    line, cut = first_line(body)
    return line + MORE * cut


def code(text):
    fence = "`" * (longest_run(text, "`") + 1)
    pad = " " * ("`" in text)
    return f"{fence}{pad}{text}{pad}{fence}"


def fenced(body):
    fence = "`" * max(3, longest_run(body, "`") + 1)
    return f"{fence}\n{body}\n{fence}"


def longest_run(text, character):
    longest = current = 0
    for c in text:
        current = current + 1 if c == character else 0
        longest = max(longest, current)
    return longest


def day(stamp):
    return time.strftime("%Y-%m-%d", time.localtime(stamp))


class Shape(NamedTuple):
    thoughts: dict
    children: dict
    tags: dict
    jumps: dict


def outline(plan):
    return list(outline_lines(ROOT_KEY, 0, shape_of(plan)))


def shape_of(plan):
    return Shape(
        {thought.key: thought for thought in plan.thoughts},
        targets(plan.links, CHILD),
        targets(plan.links, TAGGED),
        targets(plan.links, JUMP),
    )


def targets(links, relation):
    found = {}
    for link in links:
        if link.relation == relation:
            found.setdefault(link.source, []).append(link.target)
    return found


def outline_lines(key, depth, shape):
    yield "  " * depth + outline_line(key, shape)
    for child in shape.children.get(key, []):
        yield from outline_lines(child, depth + 1, shape)


def outline_line(key, shape):
    thought = shape.thoughts[key]
    title = "  ·  ".join(part for part in (thought.name, thought.label) if part)
    tags = [shape.thoughts[tag].name for tag in shape.tags.get(key, [])]
    jumps = [f"⇢ {shape.thoughts[target].name}" for target in shape.jumps.get(key, [])]
    return "  ".join([title, *tags, *jumps])
