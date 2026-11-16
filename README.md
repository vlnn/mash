# alfred-mash

Fuzzy search over a tree of plain-text records you own, from fish and from Alfred. The repository is [`vlnn/mash`](https://github.com/vlnn/mash); the workflow bundle and the Python project are named `alfred-mash`; the thing itself is just **mash**: the Alfred keyword is `m`, the fish command is `mash`, the records live in `~/.mash`.

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

See also [docs/MANUAL.md](docs/MANUAL.md): a task-by-task walkthrough on the sample tree in `examples/`, every example in it checked by the test suite. And `DESIGN.md`: what each feature is for, one example each, and how they combine.

## Contents

- [Quick start](#quick-start)
- [The built-in manual](#the-built-in-manual)
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
- [TheBrain](#thebrain)
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
m weight now => weight kg                  ↩ a rule: resolving it finds the most recently touched "weight kg" record
m weight now                               ↩ shows and copies 80
m work/ k8s ctx staging -> kubectl config use-context staging
                                           ↩ adds under the node work/, creating it
m work/                                    work/'s folders, then everything in work/
m                                          the root's folders, then everything, most recently touched first
m help/ arrow                              searches the manual that ships with mash
```

`m` is the Alfred keyword; in fish the command is `mash` and takes the same text.

## The built-in manual

mash ships a manual of itself as records, mounted read-only at the node `help/`. The files are the `help/` folder of this repository and travel inside the workflow; nothing is copied into your tree.

```
m help/                 the manual's folders, one per topic, then its records
m help/ delete          opt-enter delete  ·  deletes the file and its journal lines; there is no undo
m help/keys/            everything about ↩ and the other keys
m help/ quiz            ↩ a rule over the whole manual: the entry you have gone longest without seeing
mash help/ tilde        the same from fish: reverses time: least recently touched first
```

- Manual records are found **only when the query names `help/`**. A bare `m`, `m delete`, `mash -l` and your own rules see your records and nothing else. `help/` itself shows once, as a folder row on a bare `m`, which is also the first thing a new install lists.
- In every other way they are records: ↩ copies, ⌘L shows Large Type, a touch goes to your journal under the record's id, and a rule of yours may point at them (`review ~> help/keys/`).
- The mount is read-only. ⌥↩ is switched off on its rows, folder rows included, and `mash forget` refuses without asking. Adding under `help/` writes to your own tree (`~/.mash/help/`); such a record is yours, found everywhere and deletable.
- Every shipped fact copies on ↩: none opens or hands off, and every blank has a default. That keeps `quiz ~> help/` going round without a stall. `tests/test_help.py` checks each record, and that the bundle carries all of them.

## The tree

Everything lives under one folder, `~/.mash` by default.

- A **node** is a folder. The root folder is the root node.
- A **record** is a `*.txt` file. Its first line is the head and the arrow; the rest is the body.
- A **subfolder** is a child node. Nesting is unlimited.
- A node exists exactly when its folder does. Adding under `work/k8s/` creates the folders on the way.
- Every record mash writes gets an **id**: six random letters and digits, carried in the file name as `slug.id.txt`. The id is the record's identity: the journal refers to it, so you can edit the head, rename the slug part, or move the file to another node and its history follows. Two records with the same head are two records, as long as something else differs: the node, the arrow or the body. A file you create by hand without an id is identified by its place instead (`work/notes` for `work/notes.txt`), which holds until you rename or move it.
- The **slug** is derived from the head: lowercase, words joined by `-`, anything that is not a letter, digit or `-` dropped, `#` tags kept as words (`weight kg #body` → `weight-kg-body`). It is for you and your editor; search never reads file names.

```
~/.mash/
├── ssh-prod-web.k3f9ab.txt          root node
├── weight.p0q2mz.txt
├── work/
│   ├── k8-ctx.7xw1ue.txt            node work/
│   └── k8s/
│       └── ctx-staging.ab9d2c.txt   node work/k8s/
└── body/
    ├── weight-kg-body.x81pq2.txt    node body/
    └── notes.txt                    hand-made, no id
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
paper sizes -> A4 210 x 297 mm, Letter 8.5 x 11 in
ports -> 22 ssh, 53 dns, 80 http, 443 https
bins go out on thursday
```

Only the first arrow on a line counts, so `->` inside the body is just text:

```
c pointer -> int *p = &x;  // x -> p
```

A line without an arrow is a fact whose body is its own words: `bins go out on thursday` is searched by those words and copies them.

### Rules

Any arrow other than `->` means *search*: the right-hand side is a query, not a value. Resolving the rule runs the query and takes the best hit.

```
weight now => weight kg
weight ~> weight kg
k8 => kubernetes kube
reading now => #reading
```

- `weight now` resolves to the most recently touched record matching `weight kg`, which today is probably `weight kg #body -> 80` and tomorrow is whatever you added last.
- `weight` runs the same search the other way round: it resolves to the `weight kg` record that has gone longest without a touch.
- `k8` is a synonym: searching `k8` shows the rule; ↩ resolves it to the best `kubernetes kube` hit. Synonyms are just rules.
- `reading now` is a saved view: ↩ resolves to the best-matching record tagged `#reading`. Views are just rules.

The characters before the `>` are the rule's **axes** — see [Axes and arrows](#axes-and-arrows). `=>` is the default search; `~>` is the same search with the time order reversed, least recently touched first.

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

Scores add up over the query words, so a record found through its head always outranks one found only through its body. Letters-in-order never crosses a word boundary: `kctx` does not find `k8s ctx`, `k ctx` does. Swapped letters do not match (`stgaing`), dropped letters do (`stgng`). Body words are split on punctuation as well as spaces, so a URL is many short words and `prod` does not fuzzy-match `https://grafana.example.com/d/x` through its scattered letters.

A plain word matches a tag by the tag rule below (prefix only): `read` finds `#reading`, `reading` does not find `#read`.

| you type | you get | why |
|---|---|---|
| `m` | the root's folders, then everything, most recently touched first | empty query |
| `m prod` | ssh prod web · k8s ctx prod kube | whole word |
| `m web ssh` | ssh prod web · ssh staging web | any order |
| `m stg` | ssh staging web · k8s ctx staging kube | letters in order inside *staging* |
| `m k8 prd` | k8s ctx prod kube | `k8` starts *k8s*, `prd` is letters in order inside *prod* |
| `m grf lat` | grafana latency | `grf` is letters in order inside *grafana*, `lat` starts *latency* |
| `m кав` | кава coffee | Unicode |
| `m deploy` | ssh prod web | no head has it; the body does |
| `m dply` | ssh prod web | letters in order inside the body word *deploy@10.0.1.5* |
| `m ssh prod staging` | only *Add* | every term must match |
| `m delany @kobold` | delany books | a hand-off typed in full searches by its text; the `@word` is not a search term |

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

By default: relevance first, then the shorter head, then the most recently touched; whole tree. You change that with an **arrow** at the start of the query. Each character before the `>` names an axis and its direction; characters compose left to right.

| arrow | meaning |
|---|---|
| `=>` | defaults — never needed, implied |
| `~>` | time reversed: least recently touched first |
| `/>` | structure: only the current node's subtree |
| `#>` | only records sharing one of the rule's own tags (meaningful inside a rule) |
| `~/>` | least recently touched first, within the subtree |
| `/#>` | subtree, same tags |

```
m ~> weight kg          the weight record that has gone longest without a touch, first
m ~>                    the whole tree, least recently touched first
m work/ /> ctx          inside work/, only its subtree (which node/ already implies — see below)
m work/ ~> ctx          a node term goes before the arrow; after a leading arrow it is a plain word, so  m ~> work/ ctx  finds nothing
```

Time is the last touch, not the day a record was written (see [The journal](#the-journal)), and it only breaks ties: `~>` never lifts a weaker match over a stronger one, or a longer head over a shorter one.

The same arrow in a rule's head is the rule's search spec, so `weight ~> weight kg` and typing `~> weight kg` order their hits the same way; the rule looks in its own subtree first and never at itself. `=` carries no axis, so `=~>` is just `~>`.

New axes get a new character; an arrow is a tiny composable language and that is on purpose.

### Naming a node

A term ending in `/` names a node and narrows the search to that subtree:

```
m                        body/ · work/  ·  then every record
m work/                  work/k8s/  ·  then everything under work/, including work/k8s/
m work/ ctx              ctx anywhere under work/
m work/k8s/ ctx          only in work/k8s/
m work/ k8s/ ctx         the same: node terms in a row compose into one path
m wo                     the node row  work/  ·  then matching records everywhere
```

An empty query lists the current node's folders first (the root's on a bare `m`, `work/`'s inside `work/`), empty ones included, then the records. A node row has the 📁 icon and says how many records its subtree holds; ↩ or ⇥ on it puts `work/` into the query, and ⌥↩ asks whether to delete the node (see [Forgetting](#forgetting)). Backspace over the slash to leave. Siblings and ancestors are never searched when a node is named: `work/k8s/ ctx` does not see a `ctx` in `work/`. Nothing shadows anything; if both match a wider query, both show, the better score first.

## Resolving rules

Rules resolve on ↩, never while you type. In the list a rule shows its query as subtitle, prefixed by its arrow:

```
weight                         ~> weight kg
```

On ↩:

1. The rule's query runs with the rule's arrow as spec. Its **context** is the rule's own node subtree; if that yields nothing, the whole tree. `/>` in the arrow pins it to the subtree; a `node/` term in the query names any other node.
2. The best hit is taken.
3. If that hit is a rule, go to 1 with it. Depth is capped (8); a loop stops there and says so.
4. The fact that comes out is opened, handed off or copied, as if you had pressed ↩ on it. Its `{{name=value}}` blanks take their defaults. A rule cannot prompt: if the fact has a blank without a default, ↩ answers *Fill in the blanks first* and nothing is copied; press ↩ on the fact itself to be asked.

The chain is shown as the notification (`mash --resolve weight` prints its heads without acting):

```
weight → weight kg #body → 80
```

Examples:

```
weight kg #body -> 80            added last week
weight kg #body -> 79            added today
weight ~> weight kg              resolves to 80: least recently touched first
weight now => weight kg          resolves to 79: most recently touched first
k8 => kubernetes kube
kubernetes kube ctx staging -> kubectl config use-context staging
m k8 ↩                           copies kubectl config use-context staging
```

That holds until you press one of them: resolving `weight` touches the 80, which makes it the most recently touched weight, so `weight now` returns 80 as well until something else is touched (see [The journal](#the-journal)).

A rule's query is parsed by the same grammar as the input box, so it can use tags, node names and arrows: `latest paper => #reading #ml`, `prod box => infra/ ssh prod`.

## Adding

There is no add mode and no add command in the box. Whatever you type is always offered as a new record in the **Add: …** row.

- With no matches, *Add* is the only row: a miss is ↩ away from being stored under the words you just searched for.
- With matches, *Add* is last.
- As soon as the text contains an arrow, *Add* moves to the top; the head words are still searched so you see whether such a record already exists.
- A leading `node/` makes *Add* store there, creating the node if needed. The row says so: `Add to work/k8s/ (new node)`.
- A new file is written in that node, named from the head. The folder is the source of truth; move or rename files freely.
- A record that is already in that node, with the same head, arrow and body, is not written again: ↩ touches the one that is there, so it moves up, and answers *Already there: …*. The same head with another body is a new record, which is how a series such as `weight kg` is kept.

| you type | file (`<id>` is six random characters) | contents | shown as |
|---|---|---|---|
| `ssh prod web -> ssh deploy@10.0.1.5` | `ssh-prod-web.<id>.txt` | the same line | ssh prod web |
| `standup -> {{date}};;done: {{done}}` | `standup.<id>.txt` | `standup -> {{date}}` ⏎ `done: {{done}}` | standup |
| `weight ~> weight kg` | `weight.<id>.txt` | the same line | weight |
| `http://127.0.0.1:4000` | `http-127-0-0-1-4000.<id>.txt` | the same line | http://127.0.0.1:4000 |
| `work/ k8 ctx -> kubectl …` | `work/k8-ctx.<id>.txt` | `k8 ctx -> kubectl …` | k8 ctx |
| `ssh prod web -> ssh deploy@10.0.1.5` again | none: it is already there | | ssh prod web, touched |
| `ssh prod web -> ssh deploy@10.0.2.9` | `ssh-prod-web.<other id>.txt` | the same line | ssh prod web (both show) |

A query that is itself usable — `@kw` at either end, a URL, an existing path, or text with `{{…}}` — *and* that found something also gets a **Run: …** row between the hits and *Add*; it acts on the text without storing it. In practice that is the hand-off: the `@word` is not a search term, so `delany @kobold` finds *delany books* and offers *Run*, while a typed URL seldom matches a record and gets only *Add*.

## What ↩ does

| body | ↩ |
|---|---|
| `http://…`, `https://…`, `file://…` | opens it |
| a path that exists (`~/notes`, `/Users/me/doc.pdf`) | opens it |
| `text @keyword` or `@keyword text` | opens Alfred with `keyword text` — another workflow takes over |
| anything with `{{name}}` | asks for each blank, then one of the above with the result |
| a rule | resolves it, then opens, hands off or copies the fact it reaches (blanks take their defaults, see [Resolving rules](#resolving-rules)) |
| anything else | copies it, newlines intact |

Whatever ↩ does, the value is also *shown*: Alfred posts it as a notification, fish prints it.

| keys | action |
|---|---|
| ⇧↩ | copy and paste into the frontmost app |
| ⌘↩ | open the record's file in your editor |
| ⌥↩ | delete the record (and its journal lines); switched off on `help/` rows |
| ⌥↩ on a folder row | ask, then delete the node: its folder, everything under it and every journal line under it; switched off on the manual's folders |
| ⌃ (hold) | the record's file and what ↩ will do; for a rule, its arrow and query |
| ⌘C | copy the body as written, placeholders unfilled |
| ⌘L | large type |

These keys are for record rows. The *Add* and node rows take ↩ only; on *Run*, ⇧↩ pastes.

A shell one-liner is never run on ↩; ⇧↩ into a terminal you are looking at is one keystroke more and much harder to regret.

Only a leading or trailing `@word` is a hand-off, so `me@example.com` copies as text. Aliases for workflow names go in the `flows` setting: `tally=t kobold=kb` lets you write `parser lexer @tally`.

## The journal

`~/.mash/.journal.log` is an append-only file with one line per **touch**: every ↩, ⇧↩, add, `mash WORDS` in fish, and every step of a resolution, as `seconds ␉ identity ␉ node ␉ action`. The identity is the record's id, or its place for a hand-made file; the node is there for `forget --node` and for reading, `.` being the root. The action is the key, not its effect: `copy` for ↩ whatever ↩ then did, `paste` for ⇧↩, `print` from the CLI, `add`.

```
1793528884.768	7xw1ue	work/k8s	copy
1793528884.887	p0q2mz	body	copy
1793528884.889	x81pq2	body	copy
```

The last two lines are one ↩ on a rule: the rule, then the fact it reached. Listing, `mash -l` and `mash --resolve` never touch.

Resolving a rule touches every step, including the fact it lands on. So after `weight ~> weight kg` has returned the oldest weight, that record is the most recently touched one, and `weight now => weight kg` returns it too until something else is touched. Reading through a rule is a use, and the time axis is about use; if you want the time axis to mean "created", that is the parked journal-as-body idea below.

It is what the time axis reads: a record's time is its last journal line, or its file's modification time if it has none. Records never carry timestamps themselves, so files stay clean to hand-edit, and a tree with no journal still searches, newest file first.

When the journal passes a size (10,000 lines) it is compacted on the next write to one line per record: last touch plus a count. Nothing runs in the background. The `.log` is the first implementation; it becomes SQLite when it is measurably the slow part, with the same lines as its schema.

Deleting the journal loses ordering and nothing else.

Two ideas are parked here on purpose, to revisit once rules work: a record whose body *is* its journal (`weight kg ->` with no value, each ↩ appending a dated line, `~>` and `=>` then picking oldest or newest inside it), and journal lines being searchable like records.

## Forgetting

Removal is a command, not a keystroke, except ⌥↩, which does the same for one record, or for one node after asking:

```
mash forget prod web            removes the best-matching record and its journal lines, after confirming
mash forget --node work/k8s/    removes a node: its folder, and every journal line under it
mash forget --journal prod web  keeps the record, drops its history (it becomes "untouched")
```

`forget` prints what it is about to remove and waits for `y`. Before deleting, the file's head is compared with what the search saw, so a record whose head was edited while it waited is reported and kept; a changed body is not noticed. ⌥↩ has no such check: it deletes the file as it is at that moment. Neither removes a `help/` record.

A node is too much to lose to one keystroke, so ⌥↩ on a folder row asks first. The box lists two answers:

```
Keep work/k8s/                             nothing is deleted
Delete work/k8s/ and its 3 records         the folder, everything under it and its history; no undo
```

Keeping is the top row, so a second ↩ out of habit does nothing; deleting takes ↓ ↩. Typing in that box changes nothing, and Esc keeps the node too. An empty node reads `Delete spare/, which is empty`, which is the way to clear a folder left behind when its last record went.

Only a folder of your own tree that mash lists as a node can be removed, by the key or by `forget --node`: not the manual's `help/` folders, not `..`, not a dot-folder such as `.git`. A folder of yours under `help/` is yours; deleting it counts and removes only your records, and the manual stays.

## Command line

The fish function `mash` and the script behind it take the same text as the box. fish cannot re-run on every keystroke, so the CLI is one shot: give it a query, get a result.

```
mash prod                         prints the resolved body of the best hit
mash weight                       resolves the rule, prints 80
mash -l stg                       lists every hit, one per line: score, node, head, first body line
mash -l                           lists everything, most recent first
mash help/ tilde                  searches the built-in manual; help/ works in every command
mash -l '~> weight kg'            least recently touched first (quote arrows and {{…}} for the shell)
mash add 'ssh prod web -> ssh deploy@10.0.1.5'
mash add 'work/ k8 ctx -> kubectl config use-context staging'
mash fill 'ssh {{user=root}}@{{host}}' user=deploy host=10.0.0.1
mash forget prod web
mash --resolve weight             prints the chain a rule follows
mash brain                        the tree as an outline: folders, tags, rules and where they point
mash brain sync                   mirrors that outline into TheBrain (see TheBrain)
mash --alfred stg                 Script Filter JSON, what the workflow calls
mash --act JSON                   performs a row's command (what ↩ runs)
mash --prompt JSON TYPED          the rows that ask for a blank
```

The CLI finds the tree through `MASH_FOLDER`, `~/.mash` when unset. `mash` with no words is `mash -l`. `mash WORDS` prints and neither copies nor opens: `{{date}}` and `{{time}}` are filled, other blanks are printed as written, and `mash fill` is how you fill them.

Install the fish side by linking the two functions from the checkout:

```
ln -s (pwd)/fish/mash.fish ~/.config/fish/functions/
ln -s (pwd)/fish/stash.fish ~/.config/fish/functions/
```

`mash.fish` finds `run.py` next to itself, so a checkout anywhere works; the Alfred workflow carries its own copy of the code.

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

## TheBrain

Search shows a ranked list and never the shape. `mash brain` draws the shape: every folder, every tag, every rule and where it points. `mash brain sync` puts the same picture into [TheBrain](https://thebrain.com), where it can be walked.

```
mash brain
mash  ·  53 records · last used 2026-10-21
  body  ·  4 records · last used 2026-10-20  #body
    weight  ·  ~> weight kg
    weight now  ·  => weight kg
  home  ·  18 records · last used 2026-10-21  #read  #reading
    chores  ·  3 records · last used 2026-10-20
    recipes  ·  3 records · last used 2026-10-21
    net  ·  => wifi
  work  ·  17 records · last used 2026-10-21  #ml  #reading
    cli  ·  6 records · last used 2026-10-21
    k8s  ·  3 records · last used 2026-10-19
    net  ·  => wifi
  dashboard  ·  => grafana api latency  ⇢ work
  latest ml #ml  ·  #> paper  #ml  ⇢ work
  next chore  ·  ~> home/chores/  ⇢ chores
  reading now  ·  => #reading  #reading
```

That is the sample tree in `examples/`. Nothing is sent; it is the plan `sync` would push.

| mash | TheBrain |
|---|---|
| node | a thought of type *mash node*, child of its parent folder; the root is `mash`, under the brain's home thought |
| node's label | records in its subtree and the day one of them was last touched |
| node's note | its own records, one line each, A to Z |
| rule | a thought of type *mash rule*, child of its node; label is its arrow and query; note says what it resolves to now and how often it was used |
| where a rule points | a jump link named after the arrow: to the node its query names, otherwise to the node its best hit lives in. No jump when that is the rule's own node |
| `#tag` | a tag, spelled with its `#`. It is put on the node whose facts carry it, on a rule that carries it, and on a rule that searches for it |
| fact | a line in its node's note. With `--facts`, a thought of type *mash fact*: label is the first body line, the note is the body, a URL body is attached as a link, and tags and jumps go to the fact itself |

```
mash brain sync                   create or update the mirror
mash brain sync --facts           every fact as a thought too
mash brain sync --manual          the built-in manual too, as the help/ node it is mounted at
mash brain sync --prune           also delete thoughts whose node or record is gone
```

Setup, once: TheBrain 15 with **Settings > User > Local API** switched on, the app open, and its API key in `MASH_BRAIN_KEY` (`set -Ux MASH_BRAIN_KEY …` in fish).

| setting | default | meaning |
|---|---|---|
| `MASH_BRAIN_KEY` | none | the local API key; `sync` refuses without it |
| `MASH_BRAIN_ID` | the only brain | which brain to mirror into; with several and none chosen, `sync` lists them and stops |
| `MASH_BRAIN_URL` | `http://localhost:11522`, then `:8001` | the address from the same settings page |

- **One way.** The files stay the source of truth. Renaming or moving a mirrored thought in TheBrain changes nothing in `~/.mash`, and the next sync does not notice.
- **Repeatable.** `~/.mash/.brain.json` remembers which thought stands for which node or record, by record id, so a second sync sends only what changed: a new head is a rename, a moved file is a relink, and the thought keeps its place and anything you attached to it. An unchanged tree sends nothing.
- **Your tree only, unless asked.** The built-in manual is left out: it is mash's, the same on every install, and more than a hundred records. `--manual` brings it in, on `mash brain` and on `sync` alike: `help/` and its folders become nodes, its rules become thoughts, and a rule of yours that points into `help/` gets its jump. The flags are part of what is mirrored, so sync with the same ones each time; a sync without `--manual` after one with it counts the manual's thoughts as leftovers, and `--prune` then removes them. The same holds for `--facts`.
- **Careful.** Only thoughts the mirror made are ever touched. Without `--prune` nothing is deleted; `sync` says how many thoughts have lost their record.
- **Starting over.** Delete the `mash` thought and what hangs under it in TheBrain, and delete `.brain.json`.

## Alfred

Requirements: Alfred 5 with the Powerpack, Python 3.9+ (`/usr/bin/python3` after `xcode-select --install`). No packages.

1. `make build` produces `dist/alfred-mash.alfredworkflow`; double-click it and press **Import**.
2. Configure: **Python** (absolute path), **Folder** (`~/.mash`), **Editor**, **Flows**.
3. For `@keyword` hand-offs run once in Terminal and click OK:
   `osascript -e 'tell application id "com.runningwithcrayons.Alfred" to search "m"'`

Keyword `m`, and a hotkey that opens mash straight on its browse list (unassigned by default; set it on the *Hotkey* node, hyper+M is a good one). Alfred runs the script on every keystroke and cancels a running one when you type the next letter. Rows carry no `uid`, so Alfred shows them in the order mash returns and does not reorder them by what it has learned; the journal is what moves used records up, on both surfaces.

A bare `m` without a space shows Alfred's own results (Mail, Music…) with the mash row among them; the space is what hands the query to mash. That is Alfred's rule for keywords that *require a space*. The alternative is a keyword that does not: `make build PLIST_FLAGS=--no-space` builds that bundle, and then `m` alone is the browse list — but so is `ma`, `mu` and anything else starting with `m`, so you would launch Mail some other way. The hotkey sidesteps the question: it opens mash with an empty query and nothing else in the list.

| setting | default | meaning |
|---|---|---|
| `folder` | `~/.mash` | the tree |
| `editor` | `open -t {file}` | ⌘↩ command; `{file}` is filled |
| `python` | `/usr/bin/python3` | interpreter, absolute path |
| `flows` | empty | `name=keyword` aliases for `@` hand-offs |
| `max_results` | 50 | rows sent to Alfred |

## Performance

Every keystroke is a fresh process: start Python, walk the folder, match, print. Targets and measurements, median per keystroke (`make bench`; the measurements are from a Linux VM with the system interpreter, an Apple Silicon Mac is usually faster):

| records | target | measured | of which walking the folder |
|---|---|---|---|
| 1,000 | < 40 ms | 38 ms | 9 ms |
| 5,000 | < 80 ms | 71 ms | 44 ms |
| 20,000 | < 200 ms | 190 ms | 170 ms |

One file per record means one `stat()` per record per keystroke, and without an index also one `open()` and a parse. The first version had no index and measured 41 / 120 / 435 ms, so the **index** came in: `~/.mash/.index` holds every parsed record keyed by path and mtime (a pickle, because the records have to become Python objects anyway and `pickle.load` does that in C). Each keystroke still walks the folder and `stat`s every file, parses only files that are new or changed, drops files that are gone, and rewrites the index only when something changed. The files remain the source of truth; delete `.index` any time. Because it is a pickle, loading it can run code, so keep it out of git and out of any sync that brings the tree from a machine you do not control: `echo .index >> ~/.mash/.gitignore`.

What else keeps it fast: one compiled regex per query word, tried weakest-first over the whole lowercased head so a miss costs one search; body fuzzy over a lowercased, punctuation-split copy made at parse time; the fixed cost kept to about 27 ms (interpreter 8, `re` 8, `json` 2, the rest) by importing `subprocess` and friends only when ↩ needs them; `python -S`, `NamedTuple`, no `dataclasses`, no `pathlib`.

The walk is now most of the keystroke at 20k. If that ever matters, the next steps are skipping `stat` for folders whose own mtime is unchanged (misses in-place edits, so it needs a cheap safety net) or moving the walk and the matcher to Go or Rust behind the same CLI. `bench.py --stress` uses a vocabulary where most queries match most records; `--sizes 1000,5000,20000` and `--python /path` pick the tree sizes and the interpreter.

## Limitations

- Letters-in-order stays within one word; swapped letters never match.
- Head words split on spaces and commas only; `kube:` is a word.
- The head is the first line of the file; a body cannot come before it.
- `{{name=…}}` defaults cannot contain braces.
- A path body opens only if it exists when ↩ is pressed; otherwise it is copied.
- A head cannot end in `/` and still be searched as words; `foo/` means the node.
- Rules resolve to one hit; there is no "all hits" resolution.
- A `~>` rule is a queue only over a folder (`next ~> chores/`). With a word or a tag in its query, score and then the shorter head come before time, so the same record keeps coming back unless the heads are equally long.
- In the box a node term goes before the arrow (`m work/ ~> ctx`); after a leading arrow it is read as a word. A rule's query may name a node.
- Adding into a node drops every other term ending in `/`, the body's included: `work/ docs -> open docs/` stores `docs -> open`, from Alfred and from `mash add` alike. Add without the node and move the file.
- A rule cannot prompt: blanks in the fact it reaches take their defaults, and a blank without one stops the ↩.
- The time axis is last use, not creation: reading a record through `~>` makes it the newest.
- Any term ending in `/` before the arrow names a node, wherever it stands: `m https://example.com/` offers to add to a node called `https://example.com`. Drop the trailing slash, or put the URL after `->`.
- ⌥↩ and `forget` remove the file, and on a node the whole folder. There is no undo other than your own history, so `git init` the tree.
- Without `--manual`, `mash brain` leaves the built-in manual out, so a rule of yours that points into `help/` shows as resolving to nothing.
- A rule's jump in TheBrain is where it lands at the time of the sync; it moves on the next one, not when you press ↩.
- A fact whose URL changed gets the new link attached; the old attachment stays on the thought.
- `mash brain sync` is written against TheBrain 15's local API as other clients use it and is tested against a stand-in for it, not yet against the app.
- Plain text: do not store secrets you would not keep in a dotfile.

## Development

```
uv sync
make test           pytest on the project interpreter
make test-system    the same on /usr/bin/python3
make lint           ruff check + format
make build          dist/alfred-mash.alfredworkflow
make check          build, then drive the bundle's scripts the way Alfred would
make bench
```

The Alfred plumbing (the prompt loop through an external trigger, the Arg and Vars step that keeps a row's command in `state`, the conditional on the `prompt` variable, mods) is generated and structurally tested but has not yet been clicked through in Alfred itself; that is the first thing to do on a Mac.

| path | responsibility |
|---|---|
| `mash/records.py` | record grammar: first line → head, arrow, body; `;;` from the box; file name from head ↔ `Record` |
| `mash/query.py` | box grammar: terms, `#tags`, `node/`, leading arrow ↔ `Query` |
| `mash/tree.py` | the folder: one walk → `Snapshot` (records plus every folder with its subtree count), the mtime-keyed index, write and delete files; atomic writes; read-only mounts, whose records are marked `shipped` |
| `mash/match.py` | one regex per word, the four head tiers and the body tier, scoring |
| `mash/axes.py` | the scope test (subtree, and shipped records only when a node is named) and the ordering: score, then fewer head words, then time in the arrow's direction |
| `mash/search.py` | one pass over the records: subtree, score, time of last touch → ordered `Hit`s |
| `mash/resolve.py` | rules: context, best hit, recursion, depth cap, chain |
| `mash/journal.py` | touches, last-touch lookup, use counts, compaction |
| `mash/fill.py` | placeholders and their defaults |
| `mash/actions.py` | what ↩ does for a body: open, hand off, prompt, copy |
| `mash/session.py` | `Session`, shared by both surfaces: a `Listing` (folders, hits, *Run*, *Add*) for a box text, resolution and touching, `use`, `add`, `delete`, prompt options |
| `mash/alfred.py` | renders a `Listing` and a `Prompt` as Script Filter rows, and maps a row's command back onto the `Session` |
| `mash/brain.py` | the mirror's plan, no network: a snapshot and the journal's uses → `Thought`s and `Link`s; the outline |
| `mash/brainsync.py` | pushes a plan to TheBrain's local API and remembers it in `.brain.json`: create, retitle, note, relink, prune |
| `mash/cli.py` | `mash`, `-l`, `add`, `fill`, `forget`, `brain`, `--resolve`, `--alfred`, `--act`, `--prompt` |
| `run.py` | entry point for Alfred and the fish function |
| `make_plist.py` | source of `info.plist`: keyword filter → conditional → act, or stash the command in `state` → the prompt loop → notification |
| `scripts/build.py`, `scripts/smoke.py`, `scripts/make_icons.py` | build `dist/alfred-mash.alfredworkflow`; drive it the way Alfred would; draw the icons |
| `fish/` | the `mash` and `stash` functions |
| `bench.py` | per-keystroke latency, `--stress` |
| `tests/` | pytest, `pytest-mock` for clock, clipboard and subprocess edges; `test_manual.py` runs the manual's examples |
| `docs/MANUAL.md` | the user manual: every task, shown on the sample tree |
| `help/` | the built-in manual: records written by `mash add`, mounted at `help/` and bundled by `scripts/build.py` |
| `examples/` | the sample tree, written by `mash add`, with a journal so its time order is the same for everyone |

Order of work: `bench.py` and the tree generator first (so every later step has a number), then `records.py`, `query.py`, `match.py`, `axes.py`, `tree.py`, `resolve.py`, `journal.py`, `actions.py`, `session.py`, `cli.py`, `alfred.py`.

Tests are written first. Every row of every table in this README is a parametrized case, and so is every example in the manual, run against a copy of `examples/`; each assert carries its reason:

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
