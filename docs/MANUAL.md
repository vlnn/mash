# mash User Manual

For mash 0.1.0, as of 2026-11-14. Every example runs against the sample tree in `examples/`, and `tests/test_manual.py` asserts each one against a copy of it, so the manual only shows what the suite checks.

## Contents

- [What mash is](#what-mash-is)
- [Installing](#installing)
- [How it is organised](#how-it-is-organised)
- [The sample tree](#the-sample-tree)
- [Everyday usage](#everyday-usage)
  - [Searching](#searching)
  - [Looking things up](#looking-things-up)
  - [Acting on a result](#acting-on-a-result)
  - [Adding](#adding)
  - [Editing and deleting](#editing-and-deleting)
  - [Folders](#folders)
  - [Tags](#tags)
  - [Rules](#rules)
  - [Arrows on a query](#arrows-on-a-query)
  - [Templates](#templates)
  - [Handing off to another workflow](#handing-off-to-another-workflow)
  - [Running what you typed](#running-what-you-typed)
- [The manual inside mash](#the-manual-inside-mash)
- [In the terminal](#in-the-terminal)
- [What "recent" means](#what-recent-means)
- [Configuration](#configuration)
- [Recipes](#recipes)
- [Tips, limits and troubleshooting](#tips-limits-and-troubleshooting)

## What mash is

mash finds the one-liner, link, path, snippet or plain fact you saved, from a few letters typed in any order. It has two surfaces over the same files: the keyword `m` in Alfred and the command `mash` in fish. Type `m stg k8`, press ↩, and `kubectl config use-context staging` is on your clipboard.

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

What it gives you:

- **Fuzzy search.** Any words, any order, any part of a word. `prd` finds *prod*, `grf lat` finds *grafana api latency*, and a word no head has is looked for in the body.
- **Smart ↩.** The same key copies text, opens a URL or a path, or hands a query to another Alfred workflow, depending on what the record holds.
- **Add by typing.** Whatever you searched for and did not find is offered as a new record, so a miss is one ↩ from being stored.
- **Plain text you own.** One small `.txt` file per record, in folders you can browse, edit, grep and keep in git.
- **Folders and tags.** A folder is where a record lives; a `#tag` is what it is part of, across folders.
- **Rules.** A record can hold a search instead of a value. ↩ on it runs the search and acts on what it finds, which is how synonyms, saved views and queues are made.
- **Templates.** A body can hold blanks such as `{{host}}`; mash asks for each when you use the record, and fills `{{date}}`, `{{time}}` and `{{clipboard}}` by itself.
- **A memory.** Every use is written to a journal, so what you used last comes first, in Alfred and in fish alike.

## Installing

You need macOS with Alfred 5 and the Powerpack, and Python 3.9 or newer. Nothing else is installed: no pip packages, no Homebrew formulae. `make` targets run through [uv](https://docs.astral.sh/uv/).

mash 0.1.0 has no released bundle; you build it from the source.

**Alfred**

1. Clone and build:
   ```
   git clone https://github.com/vlnn/mash && cd mash
   make build
   ```
   That writes `dist/alfred-mash.alfredworkflow`. Double-click it and press **Import**.
2. Alfred shows the configuration sheet. Leave **Python** at `/usr/bin/python3` if you have the Xcode Command Line Tools (`xcode-select --install`), or enter another interpreter's absolute path. Leave **Folder** at `~/.mash`.
3. Type `m` and a space. On an empty tree you see two rows: the folder `help/`, which is [the manual inside mash](#the-manual-inside-mash), and *Add:*. That is all it takes.
4. If you will use `@keyword` hand-offs, run this once in Terminal and click **OK** when macOS asks whether Alfred may control Alfred:
   ```
   osascript -e 'tell application id "com.runningwithcrayons.Alfred" to search "m"'
   ```

A bare `m` without the space shows Alfred's own results; the space hands the query to mash. The workflow also has a hotkey that opens mash on its browse list; it is unassigned until you set it on the *Hotkey* node.

> **0.1.0:** the workflow's wiring (the prompt loop for blanks, the modifier keys) is generated and structurally tested, and `make check` drives the bundle's scripts the way Alfred would, but it has not yet been clicked through in Alfred itself. The search, the rules, the journal and the command line are what this manual's tests cover.

**fish**

Link the two functions from the checkout:

```
ln -s (pwd)/fish/mash.fish ~/.config/fish/functions/
ln -s (pwd)/fish/stash.fish ~/.config/fish/functions/
```

`mash` takes the same text as the Alfred box and reads the same tree, `~/.mash` unless `MASH_FOLDER` says otherwise.

**Trying it with the sample tree**

The `examples/` folder is a filled-in tree, described [below](#the-sample-tree). Work on a copy, because mash writes its index and its journal into the tree it is pointed at:

```
cp -r examples ~/.mash-demo
set -x MASH_FOLDER ~/.mash-demo        # fish; in Alfred set Folder to ~/.mash-demo
```

In Alfred, also set **Flows** to `books=bk` to see the hand-off examples as printed here. Point both back at `~/.mash` when you are done.

## How it is organised

There are three things to know: the tree, the node and the record.

**The tree** is one folder, `~/.mash` by default, created on your first add. Everything mash knows is in it as plain text, so backing up, syncing or versioning your records means doing that to one folder.

**A node** is a folder in the tree. The tree's own folder is the root node; `work/` is a node, `work/k8s/` is a node inside it, and nesting has no limit. A node exists exactly when its folder does: add a record under a new name and the folder appears.

**A record** is one `.txt` file. Its first line has three parts:

```
ssh prod web -> ssh deploy@10.0.1.5
└───head───┘ └┘ └──────body───────┘
            arrow
```

- The **head** is the words you search by and the title you see.
- The **arrow** says what the rest is. `->` means *value*: the body is what you get back. Any other arrow (`=>`, `~>`, `/>`, `#>`) means *search*: the rest is a query, and the record is a [rule](#rules).
- The **body** is everything after the arrow, and every following line of the file, verbatim.

A line without an arrow is a record whose body is its own words: `bins go out on thursday` is found by those words and copies them. Only the first arrow counts, and an arrow needs a space on each side, so `->` inside a body is just text.

Files that mash writes are named `slug.id.txt`, for example `ssh-prod-web.hpu3dj.txt`. The slug is for you and your editor; search never reads it. The six-character id is the record's identity in the journal, so you can edit the head, rename the slug or move the file to another folder and its history follows. A `.txt` file you make by hand works too.

A typical day looks like this. You run a command you will need again, so you save it: `m k8s pods failing -> kubectl get pods -A --field-selector=status.phase!=Running` ↩. A week later you type `m pods fail`, ↩, and paste. When one kind of thing piles up you give it a folder: `m work/ grafana api latency -> https://…` ↩ creates `work/` on the way.

## The sample tree

This is everything in `examples/`, node by node, each line being the first line of one file. The files were written by `mash add`, and the tree ships its journal (`.journal.log`), so "most recently touched" means the same on your copy as it does here. Where the order matters, the text says which record was added later.

The root node:

```
ssh prod web -> ssh deploy@10.0.1.5
ssh staging web -> ssh deploy@10.0.2.5
email work -> name.surname@example.com
bins go out on thursday
кава coffee order -> flat white, oat milk, no sugar
ssh box -> ssh {{user=root}}@{{host}} -p {{port=22}}
standup -> {{date}} standup
wrap code -> `{{clipboard}}`
algorithms book -> algorithms @books
quick note -> @n
dashboard => grafana api latency
reading now => #reading
latest ml #ml #> paper
next chore ~> home/chores/
```

`standup` is the one multi-line record; its file continues with `done: {{done}}` and `next: {{next}}`.

`work/`, with `work/k8s/` and `work/cli/` inside it:

```
grafana api latency -> https://grafana.example.com/d/api-latency
jira ticket -> https://example.atlassian.net/browse/{{ticket}}
reply thanks review -> Thanks for the review! I have addressed the comments, PTAL.
wifi office -> CorpNet-5G
http status -> 301 moved, 304 not modified, 401 unauthorized, 403 forbidden, 429 too many requests
paper attention #reading #ml -> https://arxiv.org/abs/1706.03762
paper adam optimizer #ml -> https://arxiv.org/abs/1412.6980
net => wifi
```

```
k8s ctx staging kube -> kubectl config use-context staging
k8s ctx prod kube -> kubectl config use-context prod
k8s pods failing -> kubectl get pods -A --field-selector=status.phase!=Running
```

```
git log graph pretty -> git log --oneline --graph --decorate --all
find py rm -> find . -name '*.pyc' -exec rm {} \;
logs api -> tail -f app.log | grep ERROR
ports -> 22 ssh, 53 dns, 80 http, 443 https, 3306 mysql, 6379 redis
chmod modes -> 644 rw-r--r--, 755 rwxr-xr-x, 600 rw-------
cron fields -> minute hour day-of-month month day-of-week
```

`home/`, with `home/recipes/` and `home/chores/` inside it:

```
wifi guest -> GuestNetwork-5G
downloads folder -> ~/Downloads
address -> 221B Baker Street, London NW1 6XE
paper sizes -> A4 210 x 297 mm, Letter 8.5 x 11 in
photo sizes -> 10 x 15 cm (4 x 6 in), 13 x 18 cm (5 x 7 in)
shoe size -> EU 43, UK 9, US 10
bulbs -> hallway E27, desk lamp E14, bathroom GU10
batteries -> remote AAA, scale CR2032, smoke alarm 9V
tyre pressure -> front 2.3 bar, rear 2.1 bar
book dune #read -> Herbert, 1965
book snow crash #reading -> Stephenson, 1992
net => wifi
```

```
pancakes -> 2 eggs, 200 ml milk, 150 g flour
oven temps -> 180 C = 350 F, 200 C = 400 F, 220 C = 425 F
cup spoon ml -> 1 cup = 240 ml, 1 tbsp = 15 ml, 1 tsp = 5 ml
```

```
water plants
take out recycling
descale kettle
```

`body/`:

```
weight kg #body -> 80
weight kg #body -> 79
weight ~> weight kg
weight now => weight kg
```

## Everyday usage

One keyword does everything. In the examples, `m …` is what you type in Alfred; in fish, `mash -l …` prints the same list and `mash …` acts on its first row (see [In the terminal](#in-the-terminal)).

### Searching

Type `m` and some words. Every word must match the record: a word of its head or, failing that, a word of its body. Order does not matter, and the record may have more words than you typed. A word can match five ways, strongest first:

| You type | Matches | How | Score |
| --- | --- | --- | --- |
| `prod` | prod | whole head word | 8 |
| `pro` | prod | start of a head word | 6 |
| `rod` | prod | inside a head word | 4 |
| `prd`, `stg` | prod, staging | letters in order inside one head word | 2 |
| `dply`, `use-context` | deploy@10.0.1.5, use-context | letters in order inside one body word | 1 |

Scores add up across your words, so a record found through its head comes before one found only through its body. Ties go to the record with fewer head words, then to the one touched most recently.

On the sample tree (the *Add* row, always present, is left out):

| You type | You get | Why |
| --- | --- | --- |
| `m` | body/ · help/ · home/ · work/, then every record of yours, most recently touched first | an empty query browses |
| `m prod` | ssh prod web · k8s ctx prod kube | whole word; the shorter head first |
| `m web ssh` | ssh staging web · ssh prod web | any order; equal matches, so the one added later first |
| `m stg` | ssh staging web · k8s ctx staging kube · wifi guest | letters in order inside *staging*; the last one through its body, *GuestNetwork-5G* |
| `m k8 prd` | k8s ctx prod kube | `k8` starts *k8s*, `prd` is inside *prod* |
| `m grf lat` | grafana api latency | `grf` is inside *grafana*, `lat` starts *latency* |
| `m кав` | кава coffee order | any script works |
| `m deploy` | ssh staging web · ssh prod web | no head has it; both bodies do |
| `m dply` | ssh staging web · ssh prod web | letters in order inside the body word *deploy@10.0.1.5* |
| `m use-context` | k8s ctx prod kube · k8s ctx staging kube | a body word; a hyphen does not split it |
| `m wifi` | wifi guest · wifi office | found in `home/` and `work/` alike |
| `m ssh prod staging` | only *Add* | every word must match |
| `m kctx` | only *Add* | letters in order stay inside one word |
| `m k ctx` | k8s ctx prod kube · k8s ctx staging kube | two words, two matches |
| `m stgaing` | only *Add* | swapped letters are not tolerated |
| `m stgng` | ssh staging web · k8s ctx staging kube | dropped letters are |

A row's subtitle tells you what ↩ will do: the body's first line for something that will be copied, `Open · …` for a link or a path, `→ keyword · …` for a hand-off, and the arrow with its query (`=> wifi`) for a rule.

### Looking things up

Not everything worth keeping is a command or a link. Sizes, codes, ratios and other facts you look up go in the same way, and because the body is searched too, you find them by what they hold as well as by what they are called:

| You type | You get | Why |
| --- | --- | --- |
| `m size` | shoe size · photo sizes · paper sizes | the whole word first; of the two that only start with it, the one added later |
| `m a4` | paper sizes | *A4* is in the body |
| `m e27` | bulbs | which lamp takes which bulb |
| `m 443` | ports | a number is a word like any other |
| `m 755` | chmod modes | |
| `m tbsp` | cup spoon ml | |
| `m home/recipes/` | cup spoon ml · oven temps · pancakes | or walk into the folder and look around |

↩ copies the line. When you only want to read it, the subtitle already shows it, and ⌘L puts it on the screen in Large Type.

### Acting on a result

What ↩ does depends on the body:

| Body | ↩ | In the sample |
| --- | --- | --- |
| `http://…`, `https://…`, `file://…` | opens it | *grafana api latency* opens the dashboard |
| a path that exists | opens it | *downloads folder* opens `~/Downloads` |
| `text @keyword` or `@keyword text` | opens Alfred with `keyword text` | *algorithms book* types `bk algorithms`; *quick note* types `n` |
| anything with `{{name}}` | asks for each blank, then one of the above | *ssh box*, *jira ticket*, *standup* |
| a rule | resolves it, then one of the above with the record it reaches | *dashboard* opens the dashboard |
| anything else | copies it, newlines intact | *ssh prod web* copies `ssh deploy@10.0.1.5`; *bins go out on thursday* copies itself |

Whatever ↩ did, a notification says so: `Copied: ssh deploy@10.0.1.5`, `Opened: https://…`, `Alfred: bk algorithms`.

The other keys work on record rows:

| Keys | Action |
| --- | --- |
| ⇧↩ | copy and paste into the frontmost app |
| ⌘↩ | open the record's file in your editor |
| ⌥↩ | delete the record and its history |
| ⌥↩ on a folder row | ask, then delete the folder, everything under it and its history |
| ⌃ (hold) | show the record's file, and what ↩ will do |
| ⌘C | copy the body as written, blanks unfilled |
| ⌘L | show the body in Large Type |

A shell one-liner is copied, never run, on ↩. ⇧↩ into a terminal you are looking at is one keystroke more and far easier to undo.

### Adding

There is no add command. Whatever you type after `m` is offered as a new record in the **Add: …** row, and ↩ on it writes the file.

- With no matches, *Add* is the only row.
- With matches, *Add* is last.
- As soon as you type an arrow you are clearly writing a record, so *Add* becomes the **first** row. The head words are still searched, so you see at once whether such a record exists.
- A term ending in `/` says where: the row reads `Add to work/k8s/: …`, and `(new node)` when the folder does not exist yet.
- When you add into a folder, every other term ending in `/` is dropped, the body's included: `m work/ docs dir -> open docs/ now` stores `docs dir -> open now`. The row's title shows what will be stored. For such a body, add without the folder and move the file, or fix the file with ⌘↩.

| You type | The *Add* row | ↩ writes |
| --- | --- | --- |
| `m stgaing` | Add: stgaing | `stgaing` in the root, a record that copies itself |
| `m home/ wifi cafe -> CafeNet` | Add to home/: wifi cafe -> CafeNet | `wifi cafe -> CafeNet` in `home/` |
| `m work/ k8s/ ctx dev` | Add to work/k8s/: ctx dev | `ctx dev` in `work/k8s/` |
| `m garden/ tomatoes sown` | Add to garden/ (new node): tomatoes sown | `tomatoes sown` in a new folder `garden/` |
| `m cluster => k8s ctx staging` | Add: cluster => k8s ctx staging | a rule; the subtitle says `rule => k8s ctx staging` |

The notification confirms where it went (`Added to garden/: tomatoes sown`), and the new record is the most recently touched one, so it is at the top of a bare `m`.

Adding something that is already there stores nothing. `m home/ wifi guest -> GuestNetwork-5G` ↩ on the sample answers `Already there: wifi guest` and touches the record it found, so it moves up instead of doubling. The same holds for `mash add` and `stash` in fish. Only an exact match counts, in the same folder and with the same head, arrow and body: `m body/ weight kg #body -> 78` ↩ is a new record next to the 80 and the 79, which is what keeps a series possible.

The Alfred box is one line, so `;;` stands for a newline there: `m release notes -> ## {{version}};;- {{done}}` stores a two-line body. A literal `;;` is typed `\;;`. In a file, `;;` is just two characters.

### Editing and deleting

⌘↩ opens the record's file in your editor. The file is the record: change the head, the arrow or the body and save. To move a record, move the file; to rename a folder, rename it.

⌥↩ deletes the file as it is at that moment, and the record's journal lines. There is no undo, which is one more reason to `git init` the tree. In fish, `mash forget` does the same after asking (see [In the terminal](#in-the-terminal)).

⌥↩ on a folder row deletes the whole node, so it asks first. The box shows two rows: `Keep work/k8s/` on top and `Delete work/k8s/ and its 3 records` below it. A second ↩ therefore keeps the folder; ↓ ↩ removes it, with every record and subfolder under it and their history. Esc keeps it as well. There is no undo here either. This is also how to clear an empty folder: its row reads `Delete spare/, which is empty`.

### Folders

A term ending in `/` names a node and narrows everything to that subtree:

| You type | You get | |
| --- | --- | --- |
| `m` | body/ · help/ · home/ · work/, then every record of yours | the root's folders first; `help/` is the built-in manual |
| `m wo` | work/, then the records matching `wo` | part of a folder name shows its row |
| `m chore` | home/chores/ · next chore | folder names are matched at any depth |
| `m work/` | work/cli/ · work/k8s/, then everything under `work/` | its folders first, like the root |
| `m home/` | home/chores/ · home/recipes/, then everything under `home/` | |
| `m home/chores/` | descale kettle · take out recycling · water plants | a node with no folders of its own |
| `m work/ ctx` | k8s ctx prod kube · k8s ctx staging kube | `ctx` anywhere under `work/` |
| `m work/k8s/ ctx` | the same two | only in `work/k8s/` |
| `m work/ k8s/ ctx` | the same two | node terms in a row make one path |

A folder row has its own icon and says how many records its subtree holds (`work/` · 17 records). ↩ or ⇥ on it puts `work/ ` into the query; backspace over the slash to leave. Naming a node never looks at its siblings or its parents.

A record does not need its folder's name in its words: `wifi office` is found by `m work/ wifi` although nothing in it says *work*.

### Tags

A tag is a head word starting with `#`. Nothing defines one; it exists because records carry it. Folders are where a thing lives; tags are what it is part of, wherever it lives:

| You type | You get | Why |
| --- | --- | --- |
| `m #reading` | book snow crash #reading · paper attention #reading #ml | one in `home/`, one in `work/` |
| `m #read` | book dune #read · book snow crash #reading · paper attention #reading #ml | a term matches a tag it is a **prefix** of; the exact tag first |
| `m #ml #reading` | paper attention #reading #ml | both tags required |
| `m #reading snow` | book snow crash #reading | a tag and a word |
| `m paper` | paper sizes · paper adam optimizer #ml · paper attention #reading #ml | no tag asked for, so the untagged one is here too |

The prefix rule runs one way: `#read` finds `#reading`, but `#reading` does not find `#read`. A plain word matches tags the same way, so `m read` finds the same three records, and the rule *reading now* by its head.

### Rules

A record whose arrow is not `->` holds a search instead of a value. In the list it shows its arrow and query as the subtitle. ↩ runs the search, takes the best hit, and acts on it; if the hit is itself a rule, that one is resolved too, up to eight steps. The notification shows the chain:

| You type, then ↩ | The rule | The notification |
| --- | --- | --- |
| `m dashboard` | `dashboard => grafana api latency` | dashboard → grafana api latency → https://grafana.example.com/d/api-latency |
| `m reading now` | `reading now => #reading` | reading now → book snow crash #reading → Stephenson, 1992 |
| `m latest ml` | `latest ml #ml #> paper` | latest ml #ml → paper adam optimizer #ml → https://arxiv.org/abs/1412.6980 |
| `m work/ net` | `net => wifi` in `work/` | net → wifi office → CorpNet-5G |
| `m home/ net` | `net => wifi` in `home/` | net → wifi guest → GuestNetwork-5G |
| `m weight now` | `weight now => weight kg` | weight now → weight kg #body → 79 |
| `m weight` | `weight ~> weight kg` | weight → weight kg #body → 80 |

Each row is a different use of the same mechanism:

- **A synonym.** `dashboard` is your word for something filed under other words. ↩ opens the link, because that is what ↩ does with the record it reaches.
- **A saved view.** `reading now` resolves to the best current `#reading` record. Both have the tag, so the one touched most recently wins: the book, added after the paper.
- **A view inside your own tags.** The `#` in `#>` means *only records sharing one of my tags*. Plain `m paper` puts *paper sizes* first; `latest ml`, tagged `#ml`, never sees it.
- **Context.** A rule searches its own folder's subtree first, and the whole tree only if that finds nothing. The two `net` rules hold the same query and resolve differently because of where they live. `/` in the arrow (`/>`) pins a rule to its subtree; a `node/` in its query points it at another one.
- **Newest and oldest.** `=>` breaks ties most recently touched first; `~` in the arrow reverses that. The 79 was added after the 80, so `weight now` reaches the 79 and `weight` the 80.

Two things to know about the last one. First, time means *last touched*, not *written* (see [What "recent" means](#what-recent-means)): `m weight` ↩ touches the 80, so the next `m weight now` ↩ returns 80 too, and the next `m weight` ↩ finds the 79, which has now waited longest. Second, that same behaviour makes a rule a **queue**:

```
next chore ~> home/chores/        the record in home/chores/ that has waited longest

m next chore ↩                    next chore → water plants
m next chore ↩                    next chore → take out recycling
m next chore ↩                    next chore → descale kettle
m next chore ↩                    next chore → water plants
```

Pressing it touches the chore it returned, which sends that chore to the back. Nothing is marked done and nothing is deleted.

A queue goes round only over a folder. With a word or a tag in the rule's query the usual order applies, score first and then the shorter head, and time is left to decide between heads of equal length: `next paper ~> paper` would hand out *paper sizes* on every ↩, because its head is the shortest.

A rule cannot ask questions. If the record it reaches has blanks, those with a default take it, and one without a default stops the ↩ with *Fill in the blanks first*; press ↩ on that record itself to be asked. If the search finds nothing, the notification says `Could not resolve: nothing matches …`.

### Arrows on a query

The arrow that makes a rule also works at the start of what you type, with the same meaning:

| You type | You get | |
| --- | --- | --- |
| `m weight kg` | the 79, then the 80 | most recently touched first |
| `m ~> weight kg` | the 80, then the 79 | `~` reverses the time order |
| `m ~>` | the whole tree, least recently touched first | what you have not looked at for longest |

Each character before the `>` is one instruction: `~` reverses time, `/` keeps to the subtree, `#` keeps to the rule's own tags (it has a meaning only inside a rule), and `=` means nothing in particular, so `=>` is the plain search. They combine: `~/>` is least recently touched first, within the subtree.

With a folder, the folder goes first: `m work/ ~> ctx` lists *k8s ctx staging kube* and then *k8s ctx prod kube*, the reverse of `m work/ ctx`. After a leading arrow a folder term is read as a plain word, so `m ~> work/ ctx` finds nothing. Inside a rule the query may name a folder, as `next chore ~> home/chores/` does.

The arrow only breaks ties. It never lifts a weaker match over a stronger one: `m weight` lists the two rules before the two values whichever arrow you put in front, because their heads are shorter.

### Templates

A body with blanks is a template; the blanks are filled when you use it:

```
ssh box -> ssh {{user=root}}@{{host}} -p {{port=22}}
jira ticket -> https://example.atlassian.net/browse/{{ticket}}
wrap code -> `{{clipboard}}`
```

`{{name}}` is a blank; `{{name=value}}` gives it a default. A name is letters, digits, `_` and `-`, so `{}`, `${VAR}` and JSON are left alone. The same name twice is asked once. Three names fill themselves and are never asked: `{{date}}` is today as `2026-11-14`, `{{time}}` is now as `14:05`, `{{clipboard}}` is the clipboard. The date and the time show filled in the subtitle; the clipboard is read only on ↩.

↩ on a template opens one prompt per blank, in order of first appearance. The title is the question and the subtitle is the body as it stands; the rows are what you have typed, the default, and the clipboard:

```
m box ↩               user (1/3): root              ssh root@{{host}} -p 22
↩                     host (2/3): 10.0.0.9          ssh root@10.0.0.9 -p 22        (10.0.0.9 was on the clipboard)
db.example.com ↩      port (3/3): 22                ssh root@db.example.com -p 22
↩                     Copied: ssh root@db.example.com -p 22
```

On the last blank ↩ does what the record would normally do with the finished text: copy it, open it if it is a link, hand it off. Esc abandons with nothing copied.

A body can run over several lines, and is copied exactly as written. The sample's `standup` is this file:

```
standup -> {{date}} standup
done: {{done}}
next: {{next}}
```

↩ asks for `done` and `next`, and copies three lines with today's date in the first.

### Handing off to another workflow

A body that starts or ends with `@word` is a hand-off: ↩ opens Alfred with `word` as the keyword and the rest as its query, so the other workflow shows its own results and you pick there. That workflow needs no setup; it just sees its keyword typed.

```
algorithms book -> algorithms @books        m algo ↩   →  Alfred shows  bk algorithms
quick note -> @n                            m quick ↩  →  Alfred shows  n
```

`books` is a name, not a keyword: the **Flows** setting `books=bk` maps one to the other, so records can say `@books` and survive a change of keyword. Without the alias, `@books` types `books`.

Only a leading or trailing `@word` counts, so `name.surname@example.com` is copied as text. The first hand-off needs the one-time macOS permission from [Installing](#installing).

### Running what you typed

mash is for storing first and running second, with one exception. When what you typed is itself a hand-off *and* found something, a **Run: …** row sits between the matches and *Add*; it acts on your text and stores nothing:

```
m algorithms @books        algorithms book  ·  Run: algorithms @books  ·  Add: algorithms @books
                           ↩ on the first row uses the record you found; on Run, Alfred shows  bk algorithms
```

The `@word` is not searched for, which is why the record is found by `algorithms` alone. The same row appears for a typed link, path or `{{blank}}` text if it happens to match a record, which is rare; with no match there is only *Add*.

## The manual inside mash

mash carries a short version of this manual as records of its own, under the node `help/`. It ships inside the workflow, so it is there before you have stored anything and always matches the version you installed.

| You type | You get |
| --- | --- |
| `m` | `help/` among your own folders |
| `m help/` | a folder per topic (add, blanks, fish, journal, keys, nodes, records, rules, search, setup, start), then the entries |
| `m help/ delete` | opt-enter delete · deletes the file and its journal lines; there is no undo |
| `m help/ tilde` | tilde in an arrow · reverses time: least recently touched first |
| `m help/keys/ paste` | shift-enter paste · copies and pastes into the frontmost app |
| `m delete` | only *Add*: the manual is searched only when you name `help/` |

Three things set it apart from your own records:

- **It stays out of the way.** A bare `m`, an ordinary search, `mash -l` and your rules never see it. Naming `help/` is what brings it in.
- **It is read-only.** ⌥↩ is switched off on its rows and its folders, and `mash forget` refuses. If you add under `help/`, the record goes into your own tree and is yours.
- **It is otherwise ordinary.** ↩ copies an entry, ⌘L shows it large, using one moves it up, and a rule of yours can point at it: `review ~> help/keys/`.

**Learning it.** `help/` holds one rule, `quiz ~> help/`, a [queue](#rules) over the whole manual. `m help/ quiz` ↩ shows the entry you have gone longest without seeing, as `quiz → tilde in an arrow → reverses time: least recently touched first`, and sends it to the back. In fish you can have the question before the answer, because `--resolve` shows where the rule leads without using it:

```
function quiz
    mash --resolve help/ quiz
    read -P 'answer? ' -l _
    mash help/ quiz
end
```

## In the terminal

fish cannot re-run on every keystroke, so the command is one shot: give it the text you would type in Alfred, get a result.

```
$ mash prod
ssh deploy@10.0.1.5

$ mash weight now
79

$ mash a4
A4 210 x 297 mm, Letter 8.5 x 11 in

$ mash -l stg
  2  .             ssh staging web  ·  ssh deploy@10.0.2.5
  2  work/k8s      k8s ctx staging kube  ·  kubectl config use-context staging
  1  home          wifi guest  ·  GuestNetwork-5G

$ mash --resolve dashboard
dashboard → grafana api latency

$ mash add 'garden/ tomatoes sown'
Added to garden/: tomatoes sown

$ mash fill 'ssh {{user=root}}@{{host}} -p {{port=22}}' host=db.example.com
ssh root@db.example.com -p 22
```

| Command | Does |
| --- | --- |
| `mash WORDS` | prints the body of the best hit, a rule resolved first; exit status 0, or 1 when nothing matches |
| `mash -l [WORDS]` | lists every hit: score, node, head, first body line. `mash` alone does the same for the whole tree |
| `mash add 'HEAD -> BODY'` | stores a record; start with `node/` to choose the folder |
| `mash fill BODY name=value …` | fills blanks in a body |
| `mash --resolve WORDS` | prints the chain a rule would follow, without using anything |
| `mash forget WORDS` | removes the best hit and its history, after showing it and waiting for `y`; if the head was edited meanwhile it reports that and keeps the file (a changed body is not noticed) |
| `mash forget --journal WORDS` | keeps the record and drops its history |
| `mash forget --node work/k8s/` | removes a folder and everything under it, after `y`; only a folder mash lists as a node, so not `..` and not a dot-folder |

`mash WORDS` prints and does nothing else: no clipboard, no browser. `{{date}}` and `{{time}}` come out filled; other blanks are printed as written, and `mash fill` fills them. Because the output is plain text, it pipes:

```
mash prod | pbcopy
mash k8 stg | fish                  run the one-liner it found
mash zzz; or echo "nothing"         exit status 1 on a miss
```

Quote arrows, `#tags` and `{{…}}` for the shell: `mash -l '~> weight kg'`, `mash -l '#reading'`.

`stash`, the second function, stores the command you just ran under the words you give it:

```
$ kubectl get pods -A | grep -v Running
$ stash k8s pods broken
Added to .: k8s pods broken
```

## What "recent" means

mash keeps a journal, `.journal.log` in the tree, with one line per **touch**: each ↩ and ⇧↩ in Alfred, each `mash WORDS` in fish, each add, and each step a rule walks through, the record it lands on included. A record's time is its last touch, or its file's modification time if it has never been touched.

That is what "most recently touched first" has meant throughout: time is about *use*. Three consequences:

- What you use floats up, in both surfaces. Pressing a record in Alfred moves it up in `mash -l`, and the other way round.
- A new record starts at the top, because adding is a touch.
- Reading through a rule is a use. `m weight` ↩ reaches the 80 and so makes it the most recently touched weight.

Looking is not a touch: typing in Alfred, `mash -l` and `mash --resolve` leave the journal alone.

The records themselves never carry dates, so the files stay clean to edit by hand. Deleting the journal loses the ordering and nothing else. `mash forget --journal WORDS` drops one record's history.

## Configuration

Alfred's settings are under **Configure Workflow…** (the cog at the top right of the workflow). Every field has a default.

| Setting | Variable | Default | What it does |
| --- | --- | --- | --- |
| Python | `python` | `/usr/bin/python3` | Interpreter, 3.9 or newer; an absolute path, no `~`. |
| Folder | `folder` | `~/.mash` | The tree. `~` is expanded. |
| Editor | `editor` | `open -t {file}` | Command run by ⌘↩; `{file}` is filled in. |
| Flows | `flows` | empty | Aliases for hand-offs as `name=keyword` pairs: `books=bk notes=n`. |
| Max results | `max_results` | `50` | Record rows sent to Alfred per keystroke. |

Alfred runs workflows with a minimal `PATH`, so give the full path of your editor's command-line tool, quoted if it has spaces: `'/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code' {file}`, `/usr/local/bin/zed {file}`.

In fish the tree is `MASH_FOLDER`, and `~/.mash` when that is unset.

## Recipes

**A log you read from both ends.** Keep adding values under the same head, and let two rules pick:

```
m body/ weight kg #body -> 78     ↩ a new value; adding touches it, so it is the newest
m weight now ↩                    the value touched last
m ~> weight kg                    the values, the one that has waited longest first
```

**A reading list.** Tag what you want to read wherever it is filed, and keep one rule as the way in:

```
m work/ paper attention #reading #ml -> https://arxiv.org/abs/1706.03762
m home/ book snow crash #reading -> Stephenson, 1992
m reading now => #reading
m #reading                        the whole list
m reading now ↩                   the one you touched last
```

**A queue.** Put the items in a folder and one `~>` rule outside it, as `next chore` does in the sample. Each ↩ hands out the item that has waited longest and sends it to the back.

**The same word, a different answer per place.** Give `work/` and `home/` a rule each with the same head and query (`net => wifi`); `m work/ net` ↩ and `m home/ net` ↩ answer from their own folders.

**Sync and history.** The tree is a folder of text files, so point **Folder** at a place your sync service watches, or keep it in git:

```
cd ~/.mash && git init
echo .index >> .gitignore
```

Leave `.index` out: it is a cache mash rebuilds, and since it is a pickle, loading one that came from somewhere else can run code. `.journal.log` is yours to decide: commit it and your ordering travels with the tree.

**Storing the command you just ran.** `stash k8s pods broken` in fish, as shown [above](#in-the-terminal).

## Tips, limits and troubleshooting

**Tips**

- Put the words you will *think of* in the head, not a description. `k8s ctx staging kube` is found from `stg`, `kube`, `ctx` or `k8`; "switch the cluster context to staging" is not.
- Let the folder carry what the words do not. Under `work/`, a record does not need *work* in its head.
- Store the facts you keep looking up, not only commands: sizes, codes, ratios. The body is searched, so `m a4` finds *paper sizes* without your remembering what you called it.
- Use *Add* as an inbox: search, miss, ↩, and tidy the file later with ⌘↩.
- For a command you run with different arguments, store one template with blanks rather than three variants.
- Before trusting a new rule, `mash --resolve WORDS` shows where it leads without touching anything.

**Known limits**

- Swapped letters (`stgaing`) do not match; dropped letters (`stgng`) do. Letters in order stay inside one word: `kctx` does not find `k8s ctx`, `k ctx` does.
- Head words split on spaces and commas only, so `kube:` is one word.
- Time is last use, not creation, and a rule that reads a record uses it.
- A rule resolves to one record, and cannot prompt for blanks.
- A `~>` queue goes round over a folder only; over a word or a tag the shorter head keeps coming first.
- In the box a folder term goes before the arrow; after a leading arrow it is a plain word.
- Adding into a folder drops any other term that ends in `/`, in the body too.
- A term ending in `/` before the arrow always names a node, so a head or a plain line cannot contain one. `m https://example.com/` offers to add to a node called `https://example.com`; drop the trailing slash, or put the link after `->`.
- A path opens only if it exists when you press ↩; otherwise it is copied.
- A default inside `{{name=…}}` cannot contain braces.
- Deleting removes the file; there is no undo.
- `help/` is read-only and is searched only when you name it.
- The files are plain text. Do not store secrets you would not keep in a dotfile.

**Troubleshooting**

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `m` shows Mail, Music and the rest | the keyword needs a space | type `m` and a space, or set the hotkey |
| `m ` shows nothing, or Alfred reports a script error | the Python path is wrong, or uses `~` | set **Python** to an absolute path |
| A hand-off does nothing the first time | macOS has not yet allowed Alfred to control Alfred | run the `osascript` line from [Installing](#installing) and click **OK** |
| ⇧↩ copies but does not paste | Alfred lacks the Accessibility permission that sending ⌘V needs | allow Alfred under System Settings → Privacy & Security → Accessibility |
| ⌘↩ does nothing | Alfred's minimal `PATH` cannot find the editor | use the tool's full path in **Editor** |
| A link or a path copies instead of opening | the path does not exist, or the scheme is not `http`, `https` or `file` | check the path; the subtitle says `Open · …` when it will open |
| A record that should copy tries to hand off | its body starts or ends with `@word` | put a word before the handle, or end the line with a full stop |
| `Fill in the blanks first` | a rule reached a record with a blank that has no default | press ↩ on that record itself, or give the blank a default |
| `Could not resolve: stopped at depth 8` | rules that point at each other | `mash --resolve WORDS` shows the loop |
| A rule returns a different record than last time | the last ↩ touched what it returned | expected; see [What "recent" means](#what-recent-means) |
| *Add* offers a node you did not mean | a word you typed ends in `/` | drop the slash |
| fish and Alfred show different records | they read different trees | make `MASH_FOLDER` and **Folder** the same path |

**Where things are**

| What | Where |
| --- | --- |
| Your records | `~/.mash/**/*.txt`, or the folder you configured |
| The journal and the index | `.journal.log` and `.index` in that folder |
| Settings | Alfred → the workflow → **Configure Workflow…** |
| Hotkey | the *Hotkey* node in the workflow, unassigned by default |
| The built-in manual | `help/` in the workflow; in mash, `m help/` |
| The sample tree | `examples/` in the [repository](https://github.com/vlnn/mash) |
| Every rule and table | [README.md](../README.md); what each feature is for, [DESIGN.md](../DESIGN.md) |
