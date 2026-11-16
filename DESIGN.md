# mash — what each piece is for

This is the map. The README is the manual, with every rule and table; this is the shorter document that says what each feature is *for*, one example each, and then how they add up. Everything in the first part is implemented and tested. Proposals that have come up in conversation but are not built are listed at the end so they don't get mistaken for features.

## The one-sentence version

mash is a fuzzy-searchable tree of small text files, where a file is either a **value** or a **search**, and every search can be ordered by how well it matches, how recently you used it, or where it lives.

## 1. Records: one file, head on line 1

**For:** data you can `cat`, `git diff`, and edit in anything. The head is what you search by and what you see; the arrow says what the rest is.

```
ssh prod web -> ssh deploy@10.0.1.5
```

Everything after the first arrow on line 1, plus every following line verbatim, is the body. No metadata lives in the file. The file name is `slug.id.txt`: the slug is for you, the six-character id is the record's identity (section 9).

## 2. Facts and rules: `->` is a value, anything else is a search

**For:** letting a record *point* instead of *hold*. A fact ends the chain; a rule continues it.

```
weight kg #body -> 80            a fact: ↩ copies 80 and shows "Copied: 80"
weight kg #body -> 79            another fact, added a week later
weight ~> weight kg              a rule: ↩ searches "weight kg" oldest-touched first; with the two facts
                                 above that finds the 80, so ↩ copies 80 and shows "weight → weight kg #body → 80"
weight now => weight kg          the same search newest first: ↩ copies 79
k8 => kubernetes kube            a synonym is a rule: ↩ copies whatever the best "kubernetes kube" record holds
reading now => #reading          a saved view is a rule: ↩ opens the most recently touched #reading link
```

Rules resolve only on ↩, never while typing (Alfred runs the script on every keystroke; nested searches would multiply). A rule whose best hit is another rule keeps going, up to 8 steps, and the chain is shown: `weight → weight kg #body → 80`.

## 3. The arrow alphabet: axes you can compose

**For:** saying *how* to search without a second syntax. The characters before `>` each name an axis and a direction, left to right.

```
=>     defaults: relevance, then newest-touched, whole tree
~>     time reversed: oldest-touched first
/>     structure: only this record's own subtree
#>     only records sharing one of this rule's tags
~/>    oldest first, within the subtree
```

The same arrow typed at the start of a query applies to that query: `m ~> weight kg` and the rule `weight ~> weight kg` run the identical search. `=` carries no axis, so `=~>` is `~>`. New axes get new characters; this is the slot where a calendar axis would go.

## 4. The tree: folders are structure

**For:** keeping and finding things without proper names — the way your brain sometimes knows the thing but forgets what it's called. `work/cli/` is a place; you can walk into it and look around, and a record inside it doesn't need "work" or "cli" in its words. What the thing *is about* goes in the words or a tag, where search can reach it; where it *belongs* is the folder.

```
~/.mash/
├── work/
│   └── cli/
│       ├── deploy-staging.ab9d2c.txt      deploy staging #k8s -> ./deploy.sh staging
│       └── tail-api-logs.7xw1ue.txt       tail api logs -> tail -f api.log | grep ERROR
└── home/
    └── recipes/
        └── pancakes.x81pq2.txt            pancakes -> 2 eggs, 200 ml milk, 150 g flour
```

```
m work/ deploy         only under work/
m work/ cli/ deploy    the same, terms compose into a path
m #k8s                 by tag, wherever it lives
m                      the root's folders first, then everything
```

A node exists when its folder does. Naming a node in a query narrows the search to that subtree and never looks at siblings or ancestors. An empty query lists the current node's folders before its records, so the tree is browsable top-down without typing a name.

## 5. Tags: dynamic views across the tree

**For:** grouping that cuts across folders. `#reading` reaches into every node; folders are where a thing lives, tags are what it's part of.

```
paper attention #reading #ml -> https://arxiv.org/abs/1706.03762
book snow crash #reading -> Stephenson, 1992

m #reading             everything tagged #reading, anywhere
m #ml #reading snow    both tags, narrowed by a word
```

The one special rule: a term matches a tag only as a **prefix** of it. `#re` finds `#read` and `#reading`; `#reading` never finds `#read`. A plain word (`read`) matches tags the same way. Nothing defines a tag; it exists because records carry it.

## 6. Search: four head tiers, then the body

**For:** typing as little as possible, in any order, and still getting the right thing first.

| you type | matches | score |
|---|---|---|
| `prod` | the whole word *prod* | 8 |
| `pro` | the start of *prod* | 6 |
| `rod` | inside *prod* | 4 |
| `prd`, `stg` | letters in order inside *prod*, *staging* | 2 |
| `dply`, `gr ex` | letters in order inside one body word | 1 |

Every query word must match somewhere; scores add up; a head hit always beats a body-only hit. Letters-in-order never crosses a word boundary (`kctx` doesn't find `k8s ctx`; `k ctx` does), and body words are split on punctuation so a URL is many short words rather than one long one that everything fuzzy-matches.

Ties: fewer head words first (the tighter record), then most recently touched.

## 7. Adding: whatever you typed is an offer

**For:** zero friction between "I searched for it and it wasn't there" and "now it is".

```
m stgaing                      no hit → the only row is  Add: stgaing
m ssh prod web -> ssh x        an arrow → Add moves to the top, head words still searched
m work/ k8 ctx -> kubectl      adds into work/, creating it if needed
m delany @kobold               usable text with a hit → a Run row between hits and Add
```

Add is always present and, without an arrow, always last. There is no add mode.

## 8. Placeholders: blanks filled when used

**For:** commands and links with a variable part, without storing one record per value.

```
ssh box -> ssh {{user=root}}@{{host}} -p {{port=22}}
jira -> https://example.atlassian.net/browse/{{ticket}}
standup -> {{date}} standup;;done: {{done}}
```

↩ prompts for each blank in order (what you typed, the default, the clipboard), then acts on the result. `{{date}}`, `{{time}}` and `{{clipboard}}` fill themselves; the first two also show filled in the list, the clipboard is read only on ↩. `;;` is a newline when typed in Alfred's one-line box.

## 9. Ids and the journal: identity and time

**For:** remembering what you used, without writing timestamps into files.

Each record mash writes gets a six-character id in its file name. The id is its identity: edit the head, rename the slug, move the file to another folder, and its history follows. Hand-made files without an id are identified by their place.

`~/.mash/.journal.log` is one line per **touch** — every ↩, paste, add, print from the CLI, and every step a rule walks through, the fact it lands on included:

```
1793528884.887	p0q2mz	body	resolve
1793528884.887	x81pq2	body	copy
```

The time axis reads this: a record's time is its last touch, or its file's mtime if it has none. Listing never touches. `mash forget` removes a record and its lines; `forget --journal` keeps the record and drops the history.

Consequence to know: resolving `weight ~>` touches the oldest weight, so immediately afterwards it is also the *newest*. Reading through a rule counts as use.

## 10. What ↩ does: the body decides

**For:** one key, no mode. The shape of the value says what to do with it.

| body | ↩ |
|---|---|
| `https://…`, `file://…`, a path that exists | opens |
| `text @kw` / `@kw text` | hands off to another Alfred workflow with keyword `kw` |
| has `{{blanks}}` | prompts, then one of the above |
| a rule | resolves, then one of the above on what it reaches |
| anything else | copies, and shows it |

⇧↩ pastes, ⌘↩ opens the file in your editor, ⌥↩ deletes (a record at once, a folder after asking), ⌃ shows the file and the chain. A shell one-liner is never run by ↩.

## 11. The index: speed without giving up files

**For:** staying under Alfred's per-keystroke budget with one file per record.

Every keystroke is a fresh process. `~/.mash/.index` holds parsed records keyed by path and mtime; each keystroke walks the folder, `stat`s every file, parses only what changed, and rewrites the index only if something did. Files stay the source of truth; delete `.index` any time. Measured: 1k records 38 ms, 5k 71 ms, 20k 190 ms (Linux VM, system Python).

## 12. Two surfaces, one grammar

**For:** the same text meaning the same thing whether typed into Alfred or fish.

```
m weight                  Alfred: rows, ↩ resolves and copies
mash weight               fish: prints 80, exit 0 (1 on a miss), so it pipes
mash -l '~> weight kg'    the ranked list
mash add 'body/ weight kg #body -> 81'
stash k8s pods broken     fish function: stores the previous command under those words
```

Alfred adds the live list, mods, prompts and node rows; fish adds pipes and `$history`. Both go through the same `Session`; Alfred's rows are rendered from what it returns.

## 13. The mirror: the shape, drawn

**For:** seeing the whole tree at once. Search answers "where is it"; nothing above answers "what is here and how is it wired".

```
mash brain            folders, tags and rules as an indented outline, with where each rule points
mash brain sync       the same as thoughts and links in TheBrain
```

A folder is a thought, a tag is a tag, a rule is a thought with a jump link to where its search lands. Facts stay lines in their folder's note unless `--facts` asks for a thought each, and the built-in manual stays out unless `--manual` asks for it. It is a projection like the index: one way, rebuilt from the files, safe to throw away. The record id is what lets a renamed or moved record keep its thought.

---

## How they work together

**Folders × rules = context that resolves.** A rule searches its own subtree first, the whole tree only if that is empty. So `work/kubectl => k8` and `home/kubectl => k8` can both exist, and `k8` means the right cluster depending on which folder you're resolving from. `/>` pins it; a `node/` in the query redirects it.

**Rules × the time axis = a queue without a flag.** `next ~> day/` (oldest-touched in `day/`) returns the plan item you've ignored longest. Pressing it touches it, so it drops to the back, and the next press returns the next one. Done-ness is just "used recently"; nothing is marked, nothing is deleted.

**Tags × rules = views you can name.** `#reading` is a filter; `reading now => #reading` is a record you can find by its name, press, and have resolve to the best current paper. `#>` lets a rule say "only among my own tags", so `latest paper #ml #> paper` stays inside ML without naming the tag twice.

**Search tiers × tags × the body = one box for three kinds of question.** `m stg k8` (which record), `m #re` (which group), `m use-context` (which record *contains* this) are the same syntax with different tiers winning; the scores make sure a head hit outranks a body hit, and a tag prefix outranks a longer tag.

**Placeholders × rules = templates that pick their own target.** `ssh box` prompts for a host; `prod box => infra/ ssh prod` resolves to whichever `ssh prod …` record is current in `infra/` and *then* prompts for its blanks. The rule chooses the record, the blanks choose the values, ↩ does one thing.

**Add × search = the miss is the form.** Because head words are searched while you type an add, you see whether the record exists before you store it, and the folder you named is the folder it lands in. The journal counts the add as a touch, so new things start at the top of the time axis.

**Ids × the journal × files = history that survives editing.** You can reorganise the tree with `mv`, rewrite heads in vim, and the time axis still knows what you used; only the id in the file name has to survive.

**Rules × the mirror = wiring you can see.** `work/net => wifi` and `home/net => wifi` are two thoughts under two folders, each saying in its note what it finds there; `next chore ~> home/chores/` is an arrow from the root into `chores`. What "folders × rules" does is a paragraph above and a picture there.

**Two surfaces × the journal = one memory.** What you press in Alfred reorders what `mash -l` prints in fish, and what you print in fish reorders Alfred's rows.

---

## Proposed, not built

These came up in conversation and are designed but not implemented; they are listed here so they aren't mistaken for features.

- **Dated virtual nodes:** `{{date}}`, `{{date+1}}`, `{{date:%G-W%V}}` filled in rule queries at resolution; a rule whose query is a bare `node/` resolving to the node itself; `tomorrow/` as a node term resolved through a rule, so `m tomorrow/ dentist -> …` lands in `day/2026-11-02/`.
- **Fallbacks:** a `??` rule per node, found by walking up to the root, evaluated when a search or a rule finds nothing, with `{{query}}` as the missed text; several `??` rows ranked by touch, *Add* always last; shape tags (`#url`, `#num`, `#path`) so a fallback applies only to misses that look a certain way.
- **Add templates:** a `+>` arrow meaning "resolve by adding", so `body/?? +> weight kg #body -> {{query}}` turns a bare `81` typed in `body/` into `Add: weight kg #body -> 81`.
- **Journal as body:** a record whose body accumulates dated lines on each ↩, with `~>`/`=>` picking oldest or newest inside it.
- **A calendar axis** as a new arrow character, if planning days turns out to be a main use.
