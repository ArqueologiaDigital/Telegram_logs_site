export const meta = {
  name: 'topic-index-pilot',
  description: 'Topic index pilot: segment the first year of the Telegram chat into conversations, verify them, build a theme tree',
  phases: [
    { title: 'Segment', detail: 'one reader per transcript chunk: conversations with ids, titles, summaries, tags' },
    { title: 'Verify', detail: 'one skeptic per chunk re-reads the transcript and corrects or drops unsupported claims' },
    { title: 'Taxonomy', detail: 'one agent builds themes > subtopics > conversations and the front-page text' },
  ],
}

const CONV = {
  type: 'object',
  properties: {
    first_id: { type: 'integer', description: 'id of the message where the conversation starts (the link target)' },
    last_id: { type: 'integer' },
    key_ids: { type: 'array', items: { type: 'integer' }, description: 'up to 3 ids of the most informative messages' },
    title: { type: 'string' },
    summary: { type: 'string' },
    participants: { type: 'array', items: { type: 'string' } },
    tags: { type: 'array', items: { type: 'string' } },
    resources: { type: 'array', items: { type: 'object', properties: { ref: { type: 'string' }, what: { type: 'string' } }, required: ['ref', 'what'] } },
    weight: { type: 'integer', enum: [1, 2, 3] },
  },
  required: ['first_id', 'last_id', 'key_ids', 'title', 'summary', 'participants', 'tags', 'resources', 'weight'],
}
const SEGMENT = {
  type: 'object',
  properties: {
    overview: { type: 'string', description: 'one paragraph, pt-BR: what this period of the group was about' },
    conversations: { type: 'array', items: CONV },
  },
  required: ['overview', 'conversations'],
}
const VERIFIED = {
  type: 'object',
  properties: {
    overview: { type: 'string' },
    conversations: { type: 'array', items: CONV },
    corrections: { type: 'array', items: { type: 'string' }, description: 'one line per change: what was wrong and what you did' },
  },
  required: ['overview', 'conversations', 'corrections'],
}
const TAXONOMY = {
  type: 'object',
  properties: {
    intro: { type: 'string' },
    themes: { type: 'array', items: { type: 'object', properties: {
      slug: { type: 'string' }, title: { type: 'string' }, summary: { type: 'string' },
      subtopics: { type: 'array', items: { type: 'object', properties: {
        slug: { type: 'string' }, title: { type: 'string' }, summary: { type: 'string' },
        conversation_ids: { type: 'array', items: { type: 'integer' } },
      }, required: ['slug', 'title', 'summary', 'conversation_ids'] } },
    }, required: ['slug', 'title', 'summary', 'subtopics'] } },
    highlights: { type: 'array', items: { type: 'object', properties: {
      first_id: { type: 'integer' }, why: { type: 'string' } }, required: ['first_id', 'why'] } },
  },
  required: ['intro', 'themes', 'highlights'],
}

const STYLE = `Writing rules (all text you produce):
- Brazilian Portuguese, neutral and factual, third person. No praise or hype ("incrível", "fascinante"), no filler.
- State only what the messages say. If you are unsure what something refers to, say less, never guess.
- Use people's names exactly as they appear in the transcript.
- Never copy phone numbers, e-mail addresses, street addresses or other personal data into your output.
- Describe what was discussed and done, not people's personalities or behaviour.`

const FORMAT = `Transcript format: one line per message:
  #<id> <YYYY-MM-DD HH:MM> <Name> [(↪#<id replied to>)] [markers]: <text>
Markers: [encaminhada de X], [foto], [vídeo], [áudio], [GIF], [figurinha], [documento: file], [link: page title], [enquete: question]. " ⏎ " is a line break inside a message. Times are Brasília time.`

phase('Segment')
const results = await pipeline(
  args.chunks,
  c => agent(`You are building a topic index of a Telegram group's history: "Arqueologia Digital e Preservação Histórica por meio da Emulação de Dispositivos Eletrônicos", a Brazilian group about preserving historical computers and electronics (emulation, ROM dumps, documentation, replicas). The index will become the front page of the group's public archive, so readers can find the conversations that matter.

Read the transcript file ${c.path} (${c.label}, ${c.messages} messages, ids #${c.first}..#${c.last}). Read ALL of it, in parts with the Read tool's offset/limit (about 400 lines at a time) — do not skim or sample; conversations you do not read cannot be indexed.

${FORMAT}

Split the period into conversations: a conversation is a stretch of messages on one subject (it may be interleaved with other talk). Ignore greetings, jokes and small talk unless they lead somewhere. A single message counts when it shares something substantial (a document, a dump, an important link, news about a project). Expect very roughly one conversation per 20-40 messages; long technical threads are one conversation even if they last hours.

For each conversation:
- first_id: id of its first message (readers will be sent there); last_id: id of its last message; key_ids: up to 3 ids of the most informative messages. Every id MUST be an id that appears in the file.
- title: short and specific (e.g. "Dump da ROM do Patinho Feio", not "Discussão técnica").
- summary: 1-3 sentences: what was discussed, what was found, decided or shared.
- participants: names of the people who actually took part.
- tags: 1-4 topic labels, specific and canonical (a machine, project, technique or institution: "Patinho Feio", "MSX", "MAME", "dump de ROM", "Museu ..."). Reuse the same spelling for the same thing.
- resources: notable links, documents or files shared (ref = URL or file name exactly as in the transcript, what = what it is). Only substantial ones.
- weight: 3 = major (a project milestone, a long substantive discussion, a key resource); 2 = substantive; 1 = minor but worth listing.

Also write overview: one paragraph about what this period of the group was about.

${STYLE}`, { label: `segment ${c.label}`, phase: 'Segment', schema: SEGMENT }),
  (seg, c) => agent(`You are a skeptical fact-checker. Another agent read the Telegram transcript ${c.path} (${c.label}, ids #${c.first}..#${c.last}) and produced the conversation index below for a public archive. Your job is to find and fix what is wrong. Assume errors exist.

${FORMAT}

For EVERY conversation, open the transcript at its ids (use Grep for "^#<id> " to locate lines, then Read around them) and check:
1. first_id, last_id and key_ids exist in the file, first_id <= last_id, and first_id really is where this subject starts (move it if the subject started earlier).
2. Every claim in title and summary is supported by the messages in that range. Remove or correct unsupported claims, wrong attributions (who said or did what), wrong technical details, and guesses presented as facts.
3. participants really posted in that conversation.
4. resources appear in the transcript exactly as written.
Drop a conversation that is mostly invented or trivial. Merge exact duplicates. Do not add new conversations unless you notice a clearly major one that is missing (then add it, checked the same way).
Also check the overview paragraph the same way.

Return the corrected index (same fields) and, in corrections, one line per change you made. An empty corrections list means you checked everything and found nothing wrong — only claim that if true.

${STYLE}

Index to check:
${JSON.stringify(seg)}`, { label: `verify ${c.label}`, phase: 'Verify', schema: VERIFIED }),
)

const ok = results.filter(Boolean)
if (ok.length !== args.chunks.length) log(`WARNING: ${args.chunks.length - ok.length} chunk(s) failed and are missing from the taxonomy`)
const convs = ok.flatMap(r => r.conversations)
log(`${convs.length} verified conversations, ${ok.reduce((n, r) => n + r.corrections.length, 0)} corrections`)

phase('Taxonomy')
const compact = convs.map(c => ({ id: c.first_id, date_range: [c.first_id, c.last_id], title: c.title, summary: c.summary, tags: c.tags, weight: c.weight }))
const taxonomy = await agent(`You are designing the front page of the public archive of a Brazilian Telegram group about preserving historical computers and electronics ("Arqueologia Digital e Preservação Histórica por meio da Emulação de Dispositivos Eletrônicos"). This pilot covers the group's first year (2017-11-06 to 2018-10-31). Readers should be able to start from a few broad themes and drill down (progressive disclosure): front page -> theme -> subtopic -> conversation -> message.

Below are the period overviews and all verified conversations (id = the conversation's first message id). Organise them:
- intro: one paragraph for the top of the front page: what the group did in its first year.
- themes: 5 to 10 broad themes, ordered by importance to this group (not alphabetically). Each has a slug (lowercase ascii, hyphens), a title, a summary (2-4 sentences, grounded in the conversations it contains), and 2-8 subtopics.
- subtopics: specific (a machine, a project, a technique, an institution). Each has slug, title, summary (1-3 sentences) and conversation_ids, in chronological order.
- Every conversation must appear in at least one subtopic; one conversation may appear in two when it genuinely belongs to both. Do not drop any. If some conversations fit nothing else, make a final theme for them, but keep it small.
- highlights: the 8-12 most important moments of the year (first_id + why, one sentence), chronological.
Base everything on the summaries given; do not add facts that are not in them.

${STYLE}

Period overviews:
${ok.map((r, i) => `- ${args.chunks[i] ? args.chunks[i].label : ''}: ${r.overview}`).join('\n')}

Conversations:
${JSON.stringify(compact)}`, { label: 'taxonomy', phase: 'Taxonomy', schema: TAXONOMY })

return { chunks: ok, taxonomy }