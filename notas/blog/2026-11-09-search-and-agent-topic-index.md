# Search and an agent-written topic index for nine years of a Telegram group

*2026-11-09*

The archive of the Telegram group @arqueologiadigital (40,975 messages since November 2017) now
has two ways in besides reading it page by page:

- **full-text search** (`formatted/html/search.html`, built with [Pagefind](https://pagefind.app)):
  one result per message, filters by year, sender and kind, links straight to the message;
- **a topic index written by Claude agents** (`formatted/html/topicos.html`): one summary per
  group year, then themes, subtopics and conversations, each linking to the messages. 1653
  conversations in 9 years.

They answer different questions. Search finds a word you remember; the index tells you what
the group talked about when you do not know what to search for. Below is what we learned
building them. The method is in `topics/README.md` and the docstrings of `search_index.py`.

## Pagefind makes metadata searchable

Pagefind records can carry metadata (`data-pagefind-meta`) that its UI shows with each result: a
title, an image, a URL. We first put the message's URL there, and a search for "preserva"
matched all 38,431 indexed messages, because every URL contains the group's name
("…Preservação…"). Metadata values are indexed as words, even inside an element marked
`data-pagefind-ignore`. Filter values, the file path and the page's `<title>` are not.

| a word that appears only in                | found? |
|--------------------------------------------|--------|
| the indexed body                           | yes    |
| a `data-pagefind-meta` value               | yes    |
| a meta value inside `data-pagefind-ignore` | yes    |
| a `data-pagefind-filter` value             | no     |
| the file path                              | no     |
| the page `<title>`                         | no     |

(`tests/pagefind_meta_probe.py`, pagefind 1.6.0.) So our records carry no metadata at all: the
sender is a filter, and the page number, message id, date and a has-photo flag are the record's
file path, which the search page turns back into a link, a title and a thumbnail.

Two smaller Pagefind lessons:

- Its Python API answers at most about 10 records a second: the reader waits 0.1 s before each
  response (`_wait_for_responses` in `pagefind/service/__init__.py`), so 38,000 records would take
  over an hour. Writing them as small HTML files and running the CLI indexer takes about 30 s.
- Any rebuild rewrites about 3.6 MB of index files, however few messages arrived: 20 new
  messages changed 94 of the 163 word-index chunks (`tests/search_churn.py`). Rebuilt daily that
  would add ~1.3 GB a year to the site's git history, so the index is rebuilt weekly.

## Agents write the index; other agents check it

The transcript of each group year (November to October) is cut into chunks of up to ~60k
tokens. For each chunk, one agent reads all of it and splits it into conversations (first and
last message, title, summary, participants, tags, shared resources). A second agent, told to
assume errors exist, opens the transcript at every cited message and corrects or drops what the
messages do not support. Per year, a third agent groups the checked conversations into themes
and subtopics and writes the year's summary and highlights, and a fourth checks every sentence
of that against the checked conversations. Finally `topics/render.py`, plain code, checks that
every cited message exists and is not deleted.

The checkers were busy (`topics/stats.py`):

| what was checked                                | items | corrections |
|-------------------------------------------------|-------|-------------|
| conversations, against the messages (years 1-9) | 1653  | 804         |
| year summaries, themes, highlights (years 1-9)  | 9     | 351         |

About one correction for every two conversations. The typical error is not invention but
inflation: a pull request "reached MAME" while it was still open, someone "learned to compile
MAME" when the messages say they managed to build it once, work credited to the person who
posted about it rather than the person who did it.

The second row is the lesson. In the first-year pilot, the step that wrote theme summaries was
not checked, on the reasoning that it only read conversation summaries that had been checked
already. It still brought back a claim a checker had removed ("Werner aprendeu a compilar o
MAME"). Every step that writes text needs its own check, including steps that only rewrite
checked text. The full run added that check; it made 25 to 48 corrections per year. Run on the
first year too, it caught that sentence and a second error the pilot had shipped: the same
theme credited Werner with work on the CP-400 Color II driver that Felipe had done.

The render step found no broken message links in any year.

## Cost

| run           | messages | agents | tokens    | time   |
|---------------|----------|--------|-----------|--------|
| pilot, year 1 | 7808     | 9      | 1,356,191 | 14 min |
| years 2-9     | 32,664   | 68     | 8,329,065 | 49 min |
| year 1 check  |          | 1      |           |        |

Roughly 240 tokens of agent work per message, six to seven times the size of the transcripts
(about 230k tokens for year 1, 1.23M for years 2-9, as estimated by `topics/transcript.py`):
each message is read once by a writer and again, around its cited ids, by a checker.

## Profiles are opt-in

The index could describe every member. It does not: a member gets a profile page only if they
ask, listed in `topics/profiles_optin.json`. The first is the group's creator, Felipe Sanches,
whose bio was written from the index with every claim traced to a conversation, which also
showed where work he posted about was done by others.

## Reproducing

| script                                           | what                                            |
|--------------------------------------------------|-------------------------------------------------|
| `search_index.py`                                | builds the search index                         |
| `tests/pagefind_meta_probe.py`                   | which parts of a page Pagefind makes searchable |
| `tests/search_churn.py`                          | index files changed per rebuild                 |
| `topics/transcript.py`                           | transcripts and the chunk plan                  |
| `topics/workflow.js`, `topics/workflow_years.js` | the agent workflows (Claude Code Workflow tool) |
| `topics/stats.py`                                | the correction counts above                     |
| `topics/render.py`                               | the pages, and the message-id check             |
