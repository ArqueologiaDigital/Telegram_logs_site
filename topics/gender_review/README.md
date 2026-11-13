# Gender review of the topic index

The topic index (`topics/data/*.json`, `topics/crossyear.json`) and the profile bios were
written by agents that sometimes assumed a member was a man. On 2026-11-13 Felipe said that
**"L."** (also known as Acidx) and **Erin Pinheiro** are women. This directory has the review
that fixed the text about them, and the tools to repeat it for anyone else.

| file                     | question it answers / what it does                                                        |
|--------------------------|-------------------------------------------------------------------------------------------|
| `extract.py`             | which index strings name the people under review? Writes them, split in parts, as JSONL   |
| `show.py`                | what does each proposed fix look like in context? (for the human check before applying)   |
| `apply_fixes.py`         | applies a fix list; each `old` must occur exactly once at its JSON path, or it stops      |
| `fixes-2026-11-13.json`  | the 18 fixes applied on 2026-11-13 (`n` refers to the numbering `extract.py` produces)    |

## How it was done (2026-11-13)

```
python3 -I topics/gender_review/extract.py SCRATCH        # 875 strings, 333213 characters, 3 parts
# three reviewers (agents), one part each, wrote SCRATCH/fixesK.json (prompt summarized below)
python3 -I topics/gender_review/show.py SCRATCH SCRATCH/fixesK.json   # every fix read in context
python3 -I topics/gender_review/apply_fixes.py SCRATCH topics/gender_review/fixes-2026-11-13.json
```

`extract.py` must run on the text as it was before the fixes (`git stash` first) for the `n`
numbers to match; it reproduces the reviewed input exactly when run on commit 0d885a03.

Reviewer prompt, in short: L. and Erin are women; read every string; flag only words whose
referent is clearly one of them ("ele", "dele", "segundo ele", masculine participles and
adjectives such as "removido", masculine nouns, articles before the name); most "ele" in the
index refer to other people or to devices, so resolve each referent first; propose the minimal
feminine fix, with an `old` substring that occurs once.

## Result

| source                                              | fixes |
|-----------------------------------------------------|-------|
| reviewer, part 1                                    | 8     |
| reviewer, part 2                                    | 5     |
| reviewer, part 3                                    | 4     |
| regex sweep afterwards (`L. acrescentado`)          | 1     |
| **total applied**                                   | 18    |

All 18 concern L. (one also Erin: "o resumo os citava" -> "as citava", about both). No masculine
form referring to Erin was found. 11 fixes are in published text (10 conversation summaries,
such as "segundo ele", "Ele concluiu", "Perguntado por ...", and 1 cross-year topic note) and 7
in the verifiers' correction logs ("L. removido dos participantes"). Every fix was read in
context with `show.py` before being applied; none was rejected. The sweep searched for the names followed by a participle or adjective, articles
before the names, and pronouns within 120 characters after them; it found one more and many
false positives (pronouns about devices and other people), which were read and left alone.

Later the same day Felipe said that **Luciana Marques** is a woman too. The index names her
in only 7 strings (outside the participant lists); all were read directly, and none refers to
her with a masculine form, so nothing changed.

## Neutral wording for everyone else

These three are not a list of the group's women: there are many more, and nobody's gender may be
assumed, from a name or from anything else. Text about any member whose gender has not been
stated should avoid gendered forms (repeat the name, rephrase). The index as written still uses
masculine forms for many such members (for example the profile bios' closing sentence, "ele pode
pedir mudanças ou a retirada do texto"); this review only fixed the three people named above.
