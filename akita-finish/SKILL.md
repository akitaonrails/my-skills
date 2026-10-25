---
name: akita-finish
description: |
  Final readability and voice pass for Akita's blog articles (PT-BR canonical, EN sibling).
  Run AFTER the humanizer skill on every new article draft and on any substantial edit,
  before showing the text to Akita. Enforces short paragraphs, lists for enumerations,
  blockquotes for takeaways, ### subsections, italics/bold conventions, rounded numbers
  in prose, and the voice bans (no "não é X, é Y" tails, no honesty/directness signaling,
  no process asides, no effusive flourishes).
license: MIT
metadata:
  version: "1.0.0"
---

# akita-finish: finishing touches for an article

This is the third pass of the article pipeline, applied to the file on disk:

1. **Draft** the article from the brief and the sources.
2. **fact-check**: adversarial verification of every claim, number and attribution against the sources. Run the `fact-check` skill's checker prompt (references/checker-prompt.md) inside isolated `general-purpose` agents in this session: one agent for claims verifiable against local source files, one or more for web claims. Do not use the external CLI harnesses (grok/zcode/codex) unless Akita asks. Apply the corrections.
3. **humanizer**: remove AI-writing tells.
4. **akita-finish** (this skill): structure, rhythm, emphasis, numbers and voice bans.

Run it as an explicit pass over the finished text. Do not rely on having "kept the rules in mind" while composing; count and grep.

## Pass 1: structure

- **Paragraph ceiling: 4 sentences.** Count sentences in every prose paragraph (skip tables, lists, blockquotes, headings). Split anything with 5 or more at the beat boundary. Short paragraph after long paragraph is part of the voice.
- **List-shaped prose becomes a list.** A paragraph that enumerates 4+ parallel items (use cases, tasks, conditions, metrics, options, steps) becomes a bulleted or numbered list. Keep one short intro sentence before it.
- **Blockquotes for takeaways.** Put the key conclusion of a section, the TL;DR, warnings and "what this means for you" in a `>` blockquote. Also use one to break any stretch of 6 to 8 consecutive plain paragraphs with no visual break.
- **`###` subsections** to scope any `##` section longer than roughly 6 to 8 paragraphs. Headings in sentence case, no Title Case.
- **Narrative flow per section:** the point first, then the evidence, then what it means for the reader.

## Pass 2: emphasis and numbers

- **Italics** for titles of cited works (books, essays, papers, articles) and for short quoted phrases used as names.
- **Bold** for important names, products and terms on first mention, and for the single key number in a table. Never bold a whole sentence, never bold-label every list item.
- **Round numbers in prose.** "quase 100" beats "99,876"; "mais de 200" beats "211,59"; "uns 14%" beats "13,8%". Keep the exact figure only inside tables, spec sheets and code blocks, or when the exact digit is the point (a price list, a measured record). Prose gives the order of magnitude; tables give the precision.
- **Ratios over raw pairs.** "o dobro da velocidade" beats "A levou 10 ms e B levou 20 ms"; "três vezes o preço" beats two dollar figures side by side; "um erro a cada 40" beats "97,6%". Give the reader the picture; leave the two raw numbers to the table.
- **Numbers in PT-BR** use decimal comma and thousands point (1.349 ms, R$ 5,22).
- Keep every inline source link. Add one when adding a claim.

## Pass 3: voice bans (grep, then read)

Run these greps over the file and fix every hit:

```sh
grep -n "—\|–\|“\|”\|‘\|’" FILE                      # dashes and curly quotes: none allowed
grep -n -i "não é [^.]*, é \|, e não \|, não [a-z]*\.$\|, nunca " FILE   # negative tails
grep -n -i "pra ser honest\|sincer\|franco\|justiça seja\|vou ser direto\|preciso ser direto\|sem rodeios\|cirúrgic\|verdade seja dita\|devo admitir" FILE
grep -n -i "honest[ao]\|honestidade" FILE            # "honest" as emphasis ornament: banned
grep -n -i "refetchável\|deletável\|fetchável" FILE  # invented anglicism calques: banned
grep -n -i "assino embaixo\|suculent\|cutuc\|lindo de" FILE   # effusive flourishes
```

Then read for what grep cannot catch:

- "não é X, é Y" and "X, e não Y" written with other words. Rewrite as the affirmative alone.
- Process asides ("X insistiu nisso, e concordo", "o modelo fez questão de"). State the finding.
- Announcing honesty or directness in ANY form ("em lista honesta", "a honestidade primeiro", "seja franco"). The voice is straightforward by default, so every "honesto" is filler. Delete it.
- Invented anglicisms: English words dressed as Portuguese ("refetchável", "deletável", "escapável" for "escapar"). If the word is not natural PT, rephrase plainly ("que dá pra baixar de novo").
- Rule-of-three padding, false ranges, "serve como/representa" instead of "é".
- The same anglicism three or more times in nearby paragraphs; translate it.
- Refer to the author as "Akita" in third person where needed, never "Fabio".

## Pass 4: report

Tell Akita in two or three lines what the pass changed (how many paragraphs split, lists created, blockquotes added, numbers rounded, voice fixes). Then stop for review. The next step (translation, index regeneration, commit) only happens after he approves.
