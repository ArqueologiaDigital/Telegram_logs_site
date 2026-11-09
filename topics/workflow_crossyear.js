export const meta = {
  name: 'topic-index-crossyear',
  description: 'Cross-year topics: group the yearly subtopics into canonical topics, then write and check one all-years summary per topic',
  phases: [
    { title: 'Group', detail: 'one agent groups all yearly subtopics into canonical cross-year topics; code checks coverage, an agent places any left out' },
    { title: 'Write', detail: 'one agent per topic: a summary of all work on it across the years, and a note per year' },
    { title: 'Check', detail: 'one skeptic per topic checks every sentence against the verified conversation summaries' },
  ],
}

// Input: the verified year indexes in topics/data/*.json, read by the agents through
// topics/material.py. args = { root: <Telegram_logs_site path>, ids: [every subtopic id] }
// (python3 -I topics/material.py --ids). Output: topics/crossyear.json (saved by hand).

const MAT = `python3 -I ${args.root}/topics/material.py`

const GROUP = {
  type: 'object',
  properties: {
    topics: { type: 'array', items: { type: 'object', properties: {
      slug: { type: 'string', description: 'lowercase ascii, hyphens, unique' },
      title: { type: 'string' },
      scope: { type: 'string', description: 'one line, pt-BR: what belongs to this topic' },
      subtopics: { type: 'array', items: { type: 'string' }, description: 'subtopic ids, exactly as listed' },
    }, required: ['slug', 'title', 'scope', 'subtopics'] } },
  },
  required: ['topics'],
}
const REPAIR = {
  type: 'object',
  properties: {
    new_topics: { type: 'array', items: { type: 'object', properties: {
      slug: { type: 'string' }, title: { type: 'string' }, scope: { type: 'string' } }, required: ['slug', 'title', 'scope'] } },
    assign: { type: 'array', items: { type: 'object', properties: {
      subtopic: { type: 'string' }, topic: { type: 'string', description: 'slug of an existing or new topic' } }, required: ['subtopic', 'topic'] } },
  },
  required: ['new_topics', 'assign'],
}
const WRITE_PROPS = {
  summary: { type: 'string', description: 'pt-BR, 1 to 4 paragraphs separated by a blank line' },
  years: { type: 'array', items: { type: 'object', properties: {
    year: { type: 'integer', description: 'group year number (1 = 2017-11..2018-10)' },
    note: { type: 'string', description: 'one or two sentences: what happened on this topic that year' } }, required: ['year', 'note'] } },
}
const WRITE = { type: 'object', properties: WRITE_PROPS, required: ['summary', 'years'] }
const CHECKED = { type: 'object', properties: { ...WRITE_PROPS, corrections: { type: 'array', items: { type: 'string' } } },
  required: ['summary', 'years', 'corrections'] }

const STYLE = `Writing rules (all text you produce):
- Brazilian Portuguese, neutral and factual, third person. No praise or hype ("incrível", "fascinante"), no filler.
- State only what the material says. If you are unsure what something refers to, say less, never guess.
- Use people's names exactly as they appear in the material.
- Never copy phone numbers, e-mail addresses, street addresses or other personal data into your output.
- Describe what was discussed and done, not people's personalities or behaviour.`

const CONTEXT = `The archive belongs to a Brazilian Telegram group about preserving historical computers and electronics ("Arqueologia Digital e Preservação Histórica por meio da Emulação de Dispositivos Eletrônicos"), active since November 2017. Its history was indexed by group year (year 1 = November 2017 to October 2018, ..., year 9 = November 2025 to October 2026): each year has themes, each theme has subtopics, each subtopic lists conversations whose summaries were checked against the messages.`

phase('Group')
let grouping = await agent(`${CONTEXT}

Readers now want to open a subject and see everything the group did on it across ALL years. Build that layer: group the yearly subtopics into canonical cross-year topics.

Run \`${MAT} --list\` to get all ${args.ids.length} yearly subtopics, one per line: id | year | yearly theme | subtopic | number of conversations | summary. Read the whole output.

Make about 25 to 40 topics, each something a reader would look for: a machine or family of machines (e.g. Patinho Feio, Technics KN5000/KN7000, Pense Bem, Scopus, Itautec, MSX), a project (e.g. Mines, Another World), an institution or collection (e.g. the Poli/USP collection), a technique or activity (e.g. ROM dumping and decapping, MAME development, restoration, digitising documents), or the group itself (organisation, meetings, events). The same subject appears under different names in different years: put it in one topic. Order topics by importance to the group across all years.

Every subtopic id must go into exactly one topic (two only when it genuinely belongs to both). Do not drop any; if a few fit nothing, a small final topic "Outros assuntos" may hold them. Copy ids exactly. slug: lowercase ascii with hyphens, unique. scope: one line in pt-BR saying what belongs there.

${STYLE}`, { label: 'group subtopics', phase: 'Group', schema: GROUP })

// Coverage check in code: every id placed, no unknown ids.
const known = new Set(args.ids)
for (const t of grouping.topics) {
  const bad = t.subtopics.filter(s => !known.has(s))
  if (bad.length) log(`topic ${t.slug}: dropping ${bad.length} unknown id(s): ${bad.join(', ')}`)
  t.subtopics = t.subtopics.filter(s => known.has(s))
}
const placed = new Set(grouping.topics.flatMap(t => t.subtopics))
const missing = args.ids.filter(id => !placed.has(id))
log(`${grouping.topics.length} topics; ${missing.length} subtopic(s) not placed`)
if (missing.length) {
  const fix = await agent(`${CONTEXT}

Another agent grouped the yearly subtopics into these cross-year topics (slug: title — scope):
${grouping.topics.map(t => `- ${t.slug}: ${t.title} — ${t.scope}`).join('\n')}

These ${missing.length} subtopics were left out. Run \`${MAT} --subtopics ${missing.join(',')}\` to read them, and assign each to the existing topic it fits best (by slug). Only if one fits none, create a new topic for it (new_topics) and assign it there.

${STYLE}`, { label: 'place left-out subtopics', phase: 'Group', schema: REPAIR })
  if (fix) {
    for (const n of fix.new_topics) if (!grouping.topics.some(t => t.slug === n.slug)) grouping.topics.push({ ...n, subtopics: [] })
    for (const a of fix.assign) {
      const t = grouping.topics.find(t => t.slug === a.topic)
      if (t && known.has(a.subtopic) && !t.subtopics.includes(a.subtopic)) t.subtopics.push(a.subtopic)
    }
  }
  const still = args.ids.filter(id => !grouping.topics.some(t => t.subtopics.includes(id)))
  if (still.length) log(`WARNING: still not placed: ${still.join(', ')}`)
}
grouping.topics = grouping.topics.filter(t => t.subtopics.length)

const results = await pipeline(
  grouping.topics,
  t => agent(`${CONTEXT}

You are writing the page of one cross-year topic: "${t.title}" (${t.scope}). Run \`${MAT} --subtopics ${t.subtopics.join(',')}\` to get its material: the yearly subtopics that belong to it, with every conversation's checked summary, date order and participants. Read all of it.

Write:
- summary: what the group discussed and did on this topic across all the years, in chronological order, as 1 to 4 paragraphs (fewer for a small topic) separated by a blank line. Say when things happened (years or group years), who did the main work, and what came of it: what was found, built, dumped, published, merged, or left unfinished. Concrete, dense, no filler; a reader should understand the whole story of the topic from it.
- years: for each group year in which the topic appears, one or two sentences on what happened that year (year = the group year number shown in the material).

${STYLE}`, { label: `write ${t.slug}`, phase: 'Write', schema: WRITE }),
  (w, t) => agent(`${CONTEXT}

You are a skeptical fact-checker. Another agent wrote the cross-year summary below for the topic "${t.title}" (${t.scope}). The conversation summaries it was written from were already checked against the messages; this text was not, and it can overstate, merge, misdate or misattribute (e.g. turn "conseguiu compilar o MAME no Windows" into "aprendeu a compilar o MAME", or credit one person with another's work). Assume errors exist.

Run \`${MAT} --subtopics ${t.subtopics.join(',')}\` to get the material. Check EVERY sentence of summary and of each year note against it: correct or remove anything it does not support (outcomes stated more strongly than the material does, credit given to the wrong person, wrong year, facts from no conversation). Check that the year notes cover every year that appears in the material and only those. Keep the structure, order and style otherwise.

Return the corrected text (same fields) and, in corrections, one line per change. An empty list means you checked everything and found nothing wrong — only claim that if true.

${STYLE}

Text to check:
${JSON.stringify(w)}`, { label: `check ${t.slug}`, phase: 'Check', schema: CHECKED }),
)

return {
  topics: grouping.topics.map((t, i) => ({ ...t, ...(results[i] || {}), unchecked: !results[i] })),
}
