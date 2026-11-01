# mash

Fuzzy search over a tree of plain-text records you own, from fish and from Alfred.

Type a few letters, get the thing. Type something it does not have, press ↩, now it has it. A record is a text file; a folder of records is a node; the folder tree is your structure. Some records are *rules*: instead of holding a value they hold a search, and resolving them runs that search — and the searches it finds, and so on — until a value comes out.

```
m stg k8
┌──────────────────────────────────────────────────────┐
│ k8s ctx staging kube                                 │
│ kubectl config use-context staging                   │
├──────────────────────────────────────────────────────┤
│ Add: stg k8                                          │
└──────────────────────────────────────────────────────┘
  ↩ copy / open / resolve / add   ⇧↩ paste   ⌘↩ edit   ⌥↩ delete
```

## Contents

- [Quick start](#quick-start)
- [The tree](#the-tree)
- [Records](#records)
  - [Facts](#facts)
  - [Rules](#rules)
  - [Multi-line bodies](#multi-line-bodies)
  - [Tags](#tags)
  - [Placeholders](#placeholders)
- [Searching](#searching)
  - [Words](#words)
  - [Tags in a query](#tags-in-a-query)
  - [Axes and arrows](#axes-and-arrows)
  - [Naming a node](#naming-a-node)
- [Resolving rules](#resolving-rules)
- [Adding](#adding)
- [What ↩ does](#what--does)
- [The journal](#the-journal)
- [Forgetting](#forgetting)
- [Command line](#command-line)
- [Alfred](#alfred)
- [Performance](#performance)
- [Limitations](#limitations)
- [Development](#development)

## Quick start

```
m ssh prod web -> ssh deploy@10.0.1.5      ↩ adds a fact to the root node
m prod                                     ↩ shows and copies ssh deploy@10.0.1.5
m https://grafana.example.com/d/latency    ↩ adds it; later  m graf  ↩ opens it
m weight kg -> 80                          ↩ a fact
m weight ~> weight kg                      ↩ a rule: resolving it finds the most recent "weight kg" record
m weight                                   ↩ shows and copies 80
m work/ k8s ctx staging -> kubectl config use-context staging
                                           ↩ adds under the node work/, creating it
m work/                                    everything in work/
m                                          everything, most recently touched first
```

`m` is the Alfred keyword; in fish the command is `mash` and takes the same text.

## The tree

Everything lives under one folder, `~/.mash` by default.

- A **node** is a folder. The root folder is the root node.
- A **record** is a `*.txt` file. Its first line is the head and the arrow; the rest is the body.
- A **subfolder** is a child node. Nesting is unlimited.
- A node exists exactly when its folder does. Adding under `work/k8s/` creates the folders on the way.
- A **record's identity** is its node path plus its head words. That is what the journal refers to. Rename the head and the record's history starts over.
- The **file name** is derived from the head: lowercase, words joined by `-`, anything that is not a letter, digit or `-` dropped, `#` tags kept as words (`weight kg #body` → `weight-kg-body.txt`), `-2`, `-3` appended on collision. It is a convenience for you and your editor, never read by search. Edit the head inside the file and mash renames the file the next time it writes that record.

```
~/.mash/
├── ssh-prod-web.txt          root node
├── weight.txt
├── work/
│   ├── k8-ctx.txt            node work/
│   └── k8s/
│       └── ctx-staging.txt   node work/k8s/
└── body/
    └── weight-kg-body.txt    node body/
```

Files are UTF-8; words in any script work (`кава coffee -> ...`). Files not ending in `.txt` and dot-folders are ignored, so a `.git` inside the tree is fine.

## Records

A record is a **head**, an **arrow**, and whatever follows. The head is the words you search by and the title you see.

```
ssh prod web -> ssh deploy@10.0.1.5
└───head───┘ └┘ └──────body───────┘
            arrow
```

Head words are split on spaces and commas. The head is always the first line of the file.

### Facts

`->` means *literal*: the body is the value, no search happens.

```
ssh prod web -> ssh deploy@10.0.1.5
grafana latency -> https://grafana.example.com/d/api-latency
notes folder -> ~/notes
email work -> name.surname@example.com
find py rm -> find . -name '*.pyc' -exec rm {} \;
logs api -> tail -f app.log | grep ERROR
pihole update finished
```

Only the first arrow on a line counts, so `->` inside the body is just text:

```
c pointer -> int *p = &x;  // x -> p
```

A line without an arrow is a fact whose body is its own words: `pihole update finished` is searched by those words and copies them.

### Rules

Any arrow other than `->` means *search*: the right-hand side is a query, not a value. Resolving the rule runs the query and takes the best hit.

```
weight ~> weight kg
k8 => kubernetes kube
reading now => #reading
```

- `weight` resolves to the most recently touched record matching `weight kg`, which today is probably `weight kg #body -> 80` and tomorrow is whatever you added last.
- `k8` is a synonym: searching `k8` shows the rule; ↩ resolves it to the best `kubernetes kube` hit. Synonyms are just rules.
- `reading now` is a saved view: ↩ resolves to the best-matching record tagged `#reading`. Views are just rules.

The characters before the `>` are the rule's **axes** — see [Axes and arrows](#axes-and-arrows). `=>` is the default search; `~>` is the same search oldest-first.

A rule has no body of its own. If the hit it resolves to is itself a rule, that one is resolved too, until a fact comes out. See [Resolving rules](#resolving-rules).

### Multi-line bodies

The body is everything after the arrow on the first line, plus every following line of the file, verbatim: indentation, blank lines and column-0 text are all body.

```
release notes ->
## {{version}}
- {{done}}
```

```
standup ->
    {{date}} standup
    done: {{done}}
    next: {{next}}
```

Copying the second one copies the indentation too; mash never reflows a body. A head with an arrow and nothing after it has a body that starts on line 2; a one-line file has a one-line body.

In the Alfred box there is only one line, so `;;` stands for a newline:

```
release notes -> ## {{version}};;- {{done}}
```

is stored as the first example above. `;;` was chosen so shell stays intact: `find . -exec rm {} \;` and `a; b` are single lines. A literal `;;` (a `case` arm) is typed `\;;`. In files `;;` is just two characters.

### Tags

A tag is a head word starting with `#`. Nothing defines a tag; it exists because records carry it.

```
weight kg #body -> 80
paper attention #reading #ml -> https://arxiv.org/abs/1706.03762
book snow crash #reading -> Stephenson, 1992
```

Tags are searched like other words except for one rule: a query term matches a tag only when the term is a **prefix** of the tag.

| query | matches | not |
|---|---|---|
| `#re` | `#reading`, `#read` | |
| `#read` | `#read` (first), `#reading` | |
| `#reading` | `#reading` | `#read` |

An exact tag outranks a longer one. Tags are not nodes: `#reading` reaches across the whole tree, which makes them the dynamic views to the folders' fixed structure.

### Placeholders

A body may leave blanks that are asked for when the record is used:

```
ssh box -> ssh {{user=root}}@{{host}} -p {{port=22}}
jira -> https://example.atlassian.net/browse/{{ticket}}
wrap code -> `{{clipboard}}`
standup -> {{date}} standup;;done: {{done}};;next: {{next}}
```

- `{{name}}` is a blank; `name` is letters, digits, `_` and `-`, so `{}`, `${VAR}` and `{"a": 1}` are left alone.
- `{{name=value}}` has a default, used literally.
- `{{date}}` (`2026-11-01`), `{{time}}` (`14:05`) and `{{clipboard}}` fill themselves and are never asked. The clipboard is read only on ↩, never while listing.
- The same name twice is one blank.

On ↩ you get one prompt per name in order of first appearance: what you typed, the default, the clipboard. Esc abandons with nothing copied.

## Searching

Whatever you type is a query. A query is a list of terms; every plain term must match the record somewhere.

### Words

Each query word matches a head word in one of four ways, strongest first, then falls back to the body:

| query | matches | how | score |
|---|---|---|---|
| `prod` | prod | whole head word | 8 |
| `pro` | prod | start of a head word | 6 |
| `rod` | prod | inside a head word | 4 |
| `prd`, `stg` | prod, staging | letters in order inside one head word | 2 |
| `dply`, `use-context` | `ssh deploy@…`, `kubectl config use-context` | letters in order inside one body word | 1 |

Scores add up over the query words, so a record found through its head always outranks one found only through its body. Letters-in-order never crosses a word boundary: `kctx` does not find `k8s ctx`, `k ctx` does. Swapped letters do not match (`stgaing`), dropped letters do (`stgng`).

| you type | you get | why |
|---|---|---|
| `m` | everything, most recently touched first | empty query |
| `m prod` | ssh prod web · k8s ctx prod kube | whole word |
| `m web ssh` | ssh prod web · ssh staging web | any order |
| `m stg` | ssh staging web · k8s ctx staging kube | letters in order inside *staging* |
| `m k8 prd` | k8s ctx prod kube | `k8` starts *k8s*, `prd` is letters in order inside *prod* |
| `m grf lat` | grafana latency | `grf` is letters in order inside *grafana*, `lat` starts *latency* |
| `m кав` | кава coffee | Unicode |
| `m deploy` | ssh prod web | no head has it; the body does |
| `m dply` | ssh prod web | letters in order inside the body word *deploy@10.0.1.5* |
| `m ssh prod staging` | only *Add* | every term must match |

Ties go to the record with fewer head words, then to the more recently touched one.

### Tags in a query

`#x` is a filter: only records carrying a tag that starts with `x` are kept, and the tag contributes to the score like a head word (exact tag 8, prefix 6).

```
m #reading             everything tagged #reading or #readme…
m #reading snow        …narrowed by snow
m #ml #reading         both tags required
```

### Axes and arrows

Results come out of three independent orderings, called axes:

- **relevance** — the scores above
- **time** — when the record was last touched (see [The journal](#the-journal))
- **structure** — where in the tree the record lives

By default: relevance first, newest-touched breaks ties, whole tree. You change that with an **arrow** at the start of the query. Each character before the `>` names an axis and its direction; characters compose left to right.

| arrow | meaning |
|---|---|
| `=>` | defaults — never needed, implied |
| `~>` | time reversed: oldest-touched first |
| `/>` | structure: only the current node's subtree |
| `#>` | only records sharing one of the rule's own tags (meaningful inside a rule) |
| `~/>` | oldest first, within the subtree |
| `/#>` | subtree, same tags |

```
m ~> weight kg          oldest weight record first — the day you started
m ~>                    the whole tree, oldest first
m work/ /> ctx          inside work/, only its subtree (which node/ already implies — see below)
```

The same arrow in a rule's head is the rule's search spec, so `weight ~> weight kg` and typing `~> weight kg` run the identical search. `=` carries no axis, so `=~>` is just `~>`.

New axes get a new character; an arrow is a tiny composable language and that is on purpose.

### Naming a node

A term ending in `/` names a node and narrows the search to that subtree:

```
m work/                  everything under work/, including work/k8s/
m work/ ctx              ctx anywhere under work/
m work/k8s/ ctx          only in work/k8s/
m wo                     the node row  work/  ·  then matching records everywhere
```

A node row has the 📁 icon and says how many records it holds; ↩ or ⇥ on it puts `work/` into the query. Backspace over the slash to leave. Siblings and ancestors are never searched when a node is named: `work/k8s/ ctx` does not see a `ctx` in `work/`. Nothing shadows anything; if both match a wider query, both show, the better score first.

## Resolving rules

Rules resolve on ↩, never while you type. In the list a rule shows its query as subtitle, prefixed by its arrow:

```
weight                         ~> weight kg
```

On ↩:

1. The rule's query runs with the rule's arrow as spec. Its **context** is the rule's own node subtree; if that yields nothing, the whole tree. `/>` in the arrow pins it to the subtree; a `node/` term in the query names any other node.
2. The best hit is taken.
3. If that hit is a rule, go to 1 with it. Depth is capped (8); a loop stops there and says so.
4. The fact that comes out is acted on as if you had pressed ↩ on it: opened, copied, prompted for blanks.

The chain is shown as a notification and as the subtitle while ⌃ is held:

```
weight → weight kg #body → 80
```

Examples:

```
weight kg #body -> 80            added last week
weight kg #body -> 79            added today
weight ~> weight kg              resolves to 80: oldest first
weight now => weight kg          resolves to 79: newest first
k8 => kubernetes kube
kubernetes kube ctx staging -> kubectl config use-context staging
m k8 ↩                           copies kubectl config use-context staging
```

A rule's query is parsed by the same grammar as the input box, so it can use tags, node names and arrows: `latest paper => #reading #ml`, `prod box => infra/ ssh prod`.

## Adding

There is no add mode and no add command in the box. Whatever you type is always offered as a new record in the **Add: …** row.

- With no matches, *Add* is the only row: a miss is ↩ away from being stored under the words you just searched for.
- With matches, *Add* is last.
- As soon as the text contains an arrow, *Add* moves to the top; the head words are still searched so you see whether such a record already exists.
- A leading `node/` makes *Add* store there, creating the node if needed. The row says so: `Add to work/k8s/ (new node)`.
- A new file is written in that node, named from the head. The folder is the source of truth; move or rename files freely.

| you type | file | contents | shown as |
|---|---|---|---|
| `ssh prod web -> ssh deploy@10.0.1.5` | `ssh-prod-web.txt` | the same line | ssh prod web |
| `standup -> {{date}};;done: {{done}}` | `standup.txt` | `standup -> {{date}}` ⏎ `done: {{done}}` | standup |
| `weight ~> weight kg` | `weight.txt` | the same line | weight |
| `http://127.0.0.1:4000` | `http-127-0-0-1-4000.txt` | the same line | http://127.0.0.1:4000 |
| `work/ k8 ctx -> kubectl …` | `work/k8-ctx.txt` | `k8 ctx -> kubectl …` | k8 ctx |
| `ssh prod web -> …` again | `ssh-prod-web-2.txt` | | ssh prod web (both show) |

A query that is itself usable — a URL, an existing path, `@kw`, or text with `{{…}}` — also gets a **Run: …** row that acts on the text without storing it.

## What ↩ does

| body | ↩ |
|---|---|
| `http://…`, `https://…`, `file://…` | opens it |
| a path that exists (`~/notes`, `/Users/me/doc.pdf`) | opens it |
| `text @keyword` or `@keyword text` | opens Alfred with `keyword text` — another workflow takes over |
| anything with `{{name}}` | asks for each blank, then one of the above with the result |
| a rule | resolves it, then one of the above with the fact it reaches |
| anything else | copies it, newlines intact |

Whatever ↩ does, the value is also *shown*: Alfred posts it as a notification, fish prints it.

| keys | action |
|---|---|
| ⇧↩ | copy and paste into the frontmost app |
| ⌘↩ | open the record's file in your editor (on *Add*: the node's folder) |
| ⌥↩ | delete the record (and its journal lines) |
| ⌃ (hold) | file, line, and what ↩ will do; for a rule, the resolution chain |
| ⌘C | copy the body as written, placeholders unfilled |
| ⌘L | large type |

A shell one-liner is never run on ↩; ⇧↩ into a terminal you are looking at is one keystroke more and much harder to regret.

Only a leading or trailing `@word` is a hand-off, so `me@example.com` copies as text. Aliases for workflow names go in the `flows` setting: `tally=t kobold=kb` lets you write `parser lexer @tally`.

## The journal

`~/.mash/.journal.log` is an append-only file with one line per **touch**: every ↩, ⇧↩, add, and resolution step, as `time ␉ node/path ␉ head words ␉ action`.

```
2026-11-01T14:05:12	work/k8s	k8 ctx	copy
2026-11-01T14:06:40	.	weight	resolve
2026-11-01T14:06:40	body	weight kg #body	copy
```

It is what the time axis reads: a record's time is its last journal line, or its file's modification time if it has none. Records never carry timestamps themselves, so files stay clean to hand-edit, and a tree with no journal still searches, newest file first.

When the journal passes a size (10,000 lines) it is compacted on the next write to one line per record: last touch plus a count. Nothing runs in the background. The `.log` is the first implementation; it becomes SQLite when it is measurably the slow part, with the same lines as its schema.

Deleting the journal loses ordering and nothing else.

Two ideas are parked here on purpose, to revisit once rules work: a record whose body *is* its journal (`weight kg ->` with no value, each ↩ appending a dated line, `~>` and `=>` then picking oldest or newest inside it), and journal lines being searchable like records.

## Forgetting

Removal is a command, not a keystroke, except ⌥↩ which does the same for one record:

```
mash forget prod web            removes the best-matching record and its journal lines, after confirming
mash forget --node work/k8s/    removes a node: its folder, and every journal line under it
mash forget --journal prod web  keeps the record, drops its history (it becomes "untouched")
```

`forget` prints what it is about to remove and waits for `y`. Records are matched by head, so a file whose head changed since the search is reported, not clobbered.

## Command line

The fish function `mash` and the script behind it take the same text as the box. fish cannot re-run on every keystroke, so the CLI is one shot: give it a query, get a result.

```
mash prod                         prints the resolved body of the best hit
mash weight                       resolves the rule, prints 80
mash -l stg                       lists every hit, one per line: score, node, head, first body line
mash -l                           lists everything, most recent first
mash -l '~> weight kg'            oldest first (quote arrows and {{…}} for the shell)
mash add 'ssh prod web -> ssh deploy@10.0.1.5'
mash add 'work/ k8 ctx -> kubectl config use-context staging'
mash fill 'ssh {{user=root}}@{{host}}' user=deploy host=10.0.0.1
mash forget prod web
mash --alfred stg                 Script Filter JSON, what the workflow calls
mash --bench                      latency per query against the current folder
```

Because the output is plain text, it pipes:

```
mash prod | pbcopy
mash k8 | fish                    run the resolved one-liner
```

Save the command you just ran under some words (`~/.config/fish/functions/stash.fish`):

```fish
function stash --description 'Store the previous command under the given words'
    mash add "$argv -> $history[1]"
end
```

```
$ kubectl get pods -A | grep -v Running
$ stash k8s pods broken
Added to .: k8s pods broken
```

Exit status is 0 on a hit, 1 on none, so `mash prod; or echo no` works.

## Alfred

Requirements: Alfred 5 with the Powerpack, Python 3.9+ (`/usr/bin/python3` after `xcode-select --install`). No packages.

1. Import `mash.alfredworkflow`.
2. Configure: **Python** (absolute path), **Folder** (`~/.mash`), **Editor**, **Flows**.
3. For `@keyword` hand-offs run once in Terminal and click OK:
   `osascript -e 'tell application id "com.runningwithcrayons.Alfred" to search "m"'`

Keyword `m`; hyper+M opens it too. Alfred runs the script on every keystroke and cancels a running one when you type the next letter. Alfred also learns which rows you pick and moves them up; mash's journal does the same across both surfaces.

| setting | default | meaning |
|---|---|---|
| `folder` | `~/.mash` | the tree |
| `editor` | `open -t {file}` | ⌘↩ command; `{file}` is filled |
| `python` | `/usr/bin/python3` | interpreter, absolute path |
| `flows` | empty | `name=keyword` aliases for `@` hand-offs |
| `max_results` | 50 | rows sent to Alfred |
| `show_nodes` | off | list every node on an empty query |

## Performance

Every keystroke is a fresh process: start Python, walk the folder, open every record, parse, match, print. Targets, median per keystroke on an Apple Silicon Mac with the system interpreter:

| records | per keystroke |
|---|---|
| 1,000 | < 40 ms |
| 5,000 | < 80 ms |
| 20,000 | < 200 ms |

One file per record means one `open()` per record per keystroke, and that is the cost to watch. So the bench is built before the matcher: `bench.py` generates a tree of 1k, 5k and 20k single-record files and times a keystroke; `--stress` uses a vocabulary where most queries match most records. If a keystroke misses the targets, an index keyed by file mtimes (SQLite) comes in, with the files staying the source of truth. If that is still not enough, the matcher moves to Go or Rust behind the same CLI. The numbers decide, not feel.

What keeps it fast meanwhile: one compiled regex per query word whose alternatives are ordered strongest-first so a single match gives both whether and how well; body fuzzy only over a lowercased copy made at parse time; `stat` for open-or-copy only on shown rows; `python -S`, no `dataclasses`, no `pathlib`.

## Limitations

- Letters-in-order stays within one word; swapped letters never match.
- Head words split on spaces and commas only; `kube:` is a word.
- The head is the first line of the file; a body cannot come before it.
- `{{name=…}}` defaults cannot contain braces.
- A path body opens only if it exists at search time.
- A head cannot end in `/` and still be searched as words; `foo/` means the node.
- Rules resolve to one hit; there is no "all hits" resolution.
- Plain text: do not store secrets you would not keep in a dotfile.

## Development

```
uv sync
make test           pytest on the project interpreter
make test-system    the same on /usr/bin/python3
make lint           ruff check + format
make check          build mash.alfredworkflow and drive it the way Alfred would
make bench
```

| path | responsibility |
|---|---|
| `mash/records.py` | record grammar: first line → head, arrow, body; `;;` from the box; file name from head ↔ `Record` |
| `mash/query.py` | box grammar: terms, `#tags`, `node/`, leading arrow ↔ `Query` |
| `mash/tree.py` | the folder: walk nodes, read records, write and rename files, delete; atomic, symlink-safe |
| `mash/match.py` | one regex per word, the four head tiers and the body tier, scoring |
| `mash/axes.py` | relevance, time, structure as `records → records`; composition from an arrow |
| `mash/resolve.py` | rules: context, best hit, recursion, depth cap, chain |
| `mash/journal.py` | touches, last-touch lookup, compaction |
| `mash/fill.py` | placeholders and their defaults |
| `mash/actions.py` | what ↩ does for a body: open, hand off, prompt, copy |
| `mash/alfred.py` | Script Filter JSON: rows, node rows, *Add*, *Run*, prompts |
| `mash/cli.py` | `mash`, `-l`, `add`, `fill`, `forget`, `--alfred`, `--bench` |
| `make_plist.py` | source of `info.plist` |
| `bench.py` | per-keystroke latency, `--stress` |
| `tests/` | pytest, `pytest-mock` for clock, clipboard and filesystem edges |

Order of work: `bench.py` and the tree generator first (so every later step has a number), then `records.py`, `query.py`, `match.py`, `axes.py`, `tree.py`, `resolve.py`, `journal.py`, `actions.py`, `cli.py`, `alfred.py`.

Tests are written first. Every row of every table in this README is a parametrized case, each assert carrying its reason:

```python
@pytest.mark.parametrize(
    "query, head, score",
    [
        ("prod", "ssh prod web", 8),
        ("pro", "ssh prod web", 6),
        ("rod", "ssh prod web", 4),
        ("prd", "ssh prod web", 2),
        ("stgaing", "ssh staging web", 0),
    ],
)
def test_head_word_tiers(query, head, score):
    assert score_head(query, head) == score, f"{query!r} against {head!r} should score {score}"
```
