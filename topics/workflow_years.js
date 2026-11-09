export const meta = {
  name: 'topic-index-years',
  description: 'Topic index for the group years after the first: segment and verify each chunk, build and verify one theme tree and summary per year; also verify year 1',
  phases: [
    { title: 'Segment', detail: 'one reader per transcript chunk: conversations with ids, titles, summaries, tags' },
    { title: 'Verify', detail: 'one skeptic per chunk re-reads the transcript and corrects or drops unsupported claims' },
    { title: 'Taxonomy', detail: 'one agent per year: themes > subtopics > conversations, the year summary, highlights' },
    { title: 'Check taxonomy', detail: 'one skeptic per year checks every sentence of the year summary, themes and highlights against the verified conversations' },
  ],
}

// Same segment and verify prompts as topics/workflow.js (the year-1 pilot), plus: the year summary
// follows year 1's as a style example, and a check of the taxonomy step (which the pilot lacked:
// its theme summaries could bring back a claim a verifier had removed). args = plan.json from
// topics/transcript.py --years, plus year1_data (path of year 1's data file, checked again here).

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
const TAX_PROPS = {
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
}
const TAXONOMY = { type: 'object', properties: TAX_PROPS, required: ['intro', 'themes', 'highlights'] }
const TAX_CHECKED = {
  type: 'object',
  properties: { ...TAX_PROPS, corrections: { type: 'array', items: { type: 'string' } } },
  required: ['intro', 'themes', 'highlights', 'corrections'],
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

const YEAR1_INTRO = 'No primeiro ano, de novembro de 2017 a outubro de 2018, o grupo funcionou como um grupo de estudos para preservar hardware histórico, com o resgate do Patinho Feio entre os principais projetos. Boa parte do trabalho aconteceu no acervo de computadores da Poli/USP: lá foram examinados os terminais e o PC-XT Nexus 2600 da Scopus, com explicações de DQ, ex-funcionário da empresa, e foram encontradas uma teletype e a leitora de fita perfurada Facit 4021. Com o MAME, o grupo emulou máquinas nacionais como o Sagitta, o Nexus 2600, o CP-500 e o CP-400, transcreveu para netlist os esquemáticos do Atari Gran Trak 10 e montou réplicas, entre elas a placa de decodificação de opcodes do Patinho Feio e o Golly Ghost. No mesmo período foram criados a organização ArqueologiaDigital no GitHub e o site arqueologiadigital.org, ROMs, manuais e imagens de disco foram publicados, e começaram os encontros e as oficinas no Garoa Hacker Clube.'

const MONTHS = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']
const ORD = ['', 'primeiro', 'segundo', 'terceiro', 'quarto', 'quinto', 'sexto', 'sétimo', 'oitavo', 'nono', 'décimo']
const spanPt = y => `de ${MONTHS[+y.from.slice(5) - 1]} de ${y.from.slice(0, 4)} a ${MONTHS[+y.to.slice(5) - 1]} de ${y.to.slice(0, 4)}`

const segmentPrompt = c => `You are building a topic index of a Telegram group's history: "Arqueologia Digital e Preservação Histórica por meio da Emulação de Dispositivos Eletrônicos", a Brazilian group about preserving historical computers and electronics (emulation, ROM dumps, documentation, replicas). The index will become part of the front page of the group's public archive, so readers can find the conversations that matter.

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

${STYLE}`

const verifyPrompt = (c, seg) => `You are a skeptical fact-checker. Another agent read the Telegram transcript ${c.path} (${c.label}, ids #${c.first}..#${c.last}) and produced the conversation index below for a public archive. Your job is to find and fix what is wrong. Assume errors exist.

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
${JSON.stringify(seg)}`

const taxonomyPrompt = (y, ok, convs) => `You are designing part of the front page of the public archive of a Brazilian Telegram group about preserving historical computers and electronics ("Arqueologia Digital e Preservação Histórica por meio da Emulação de Dispositivos Eletrônicos"). The archive is organised by group year (each year runs November to October; the group began in November 2017). This page covers the group's ${ORD[y.year]} year, ${spanPt(y)} (${y.messages} messages). Readers start from a summary of each year and drill down (progressive disclosure): year -> theme -> subtopic -> conversation -> message.

Below are the period overviews and all verified conversations of this year (id = the conversation's first message id). Organise them:
- intro: ONE paragraph summarising the year, for the top of the year's page and for the list of years on the front page. Write it in the same style, tone and length as the first year's summary, which begins "No primeiro ano, de novembro de 2017 a outubro de 2018, ...": start with "No ${ORD[y.year]} ano, ${spanPt(y)}, ..." and cover the year's main threads in a few dense sentences. The first year's summary, as a style example only (do not copy its facts):
  "${YEAR1_INTRO}"
- themes: broad themes, ordered by importance to the group in this year (not alphabetically); about 4 to 10, fewer for a quiet year. Each has a slug (lowercase ascii, hyphens), a title, a summary (2-4 sentences, grounded in the conversations it contains), and 2-8 subtopics.
- subtopics: specific (a machine, a project, a technique, an institution). Each has slug, title, summary (1-3 sentences) and conversation_ids, in chronological order.
- Every conversation must appear in at least one subtopic; one conversation may appear in two when it genuinely belongs to both. Do not drop any. If some conversations fit nothing else, make a final theme for them, but keep it small.
- highlights: the most important moments of the year (first_id + why, one sentence), chronological; about 6 to 12, fewer for a quiet year.
Base everything on the summaries given; do not add facts that are not in them.

${STYLE}

Period overviews:
${ok.map(r => `- ${r.overview}`).join('\n')}

Conversations:
${JSON.stringify(convs)}`

const checkTaxPrompt = (yearLabel, source, tax) => `You are a skeptical fact-checker for the public archive of a Brazilian Telegram group about preserving historical computers. Another agent organised the verified conversations of ${yearLabel} into a year summary (intro), themes, subtopics and highlights. The conversation summaries have already been checked against the messages; the text written from them has not, and it can overstate, merge or misattribute (e.g. turn "conseguiu compilar o MAME no Windows" into "aprendeu a compilar o MAME"). Assume errors exist.

${source}

Check EVERY sentence of intro, of each theme and subtopic summary, and of each highlight's "why" against the conversation summaries: correct or remove anything they do not support (outcomes stated more strongly than the summaries do, credit given to the wrong person, facts from no conversation). Also check: every conversation id in subtopics and highlights is one of this year's conversations; every conversation appears in at least one subtopic (add a missing one to the subtopic it fits best); slugs are lowercase ascii with hyphens and unique within the year. Keep the structure and order unless something is broken; keep the intro's opening and style.

Return the corrected taxonomy (same fields) and, in corrections, one line per change. An empty list means you checked everything and found nothing wrong — only claim that if true.

${STYLE}

Taxonomy to check:
${JSON.stringify(tax)}`

const compact = convs => convs.map(c => ({ id: c.first_id, title: c.title, summary: c.summary, participants: c.participants, tags: c.tags, weight: c.weight }))

// chunk paths in args are relative to args.base (the transcript directory)
const years = args.years.map(y => ({ ...y, chunks: y.chunks.map(c => ({ ...c, path: `${args.base}/${c.path}` })) }))
const results = await pipeline(
  [{ year: 1, existing: true }, ...years],
  async y => {
    if (y.existing) return { existing: true }   // not null: a null stage result drops the item
    const chunks = await pipeline(
      y.chunks,
      c => agent(segmentPrompt(c), { label: `segment ${c.label}`, phase: 'Segment', schema: SEGMENT }),
      (seg, c) => agent(verifyPrompt(c, seg), { label: `verify ${c.label}`, phase: 'Verify', schema: VERIFIED }),
    )
    const ok = chunks.filter(Boolean)
    if (ok.length !== y.chunks.length) log(`WARNING year ${y.year}: ${y.chunks.length - ok.length} chunk(s) failed and are missing`)
    return ok
  },
  async (ok, y) => {
    if (y.existing) return { ok: null, tax: null }
    const convs = ok.flatMap(r => r.conversations)
    log(`year ${y.year}: ${convs.length} verified conversations, ${ok.reduce((n, r) => n + r.corrections.length, 0)} corrections`)
    const tax = await agent(taxonomyPrompt(y, ok, compact(convs)), { label: `taxonomy year ${y.year}`, phase: 'Taxonomy', schema: TAXONOMY })
    return { ok, tax }
  },
  async (prev, y) => {
    if (y.existing) {
      const checked = await agent(checkTaxPrompt('the group\'s first year (November 2017 to October 2018)',
        `Read the file ${args.year1_data} (JSON, about 240 KB; use Read with offset/limit until you have all of it): the verified conversations are in chunks[].conversations, and the taxonomy to check is its "taxonomy" field, also given below.`,
        null).replace('Taxonomy to check:\nnull', 'Taxonomy to check: the "taxonomy" field of that file.'),
        { label: 'check taxonomy year 1', phase: 'Check taxonomy', schema: TAX_CHECKED })
      return { year: 1, taxonomy: checked }
    }
    if (!prev.tax) return { year: y.year, from: y.from, to: y.to, messages: y.messages, chunks: prev.ok, taxonomy: null }
    const convs = compact(prev.ok.flatMap(r => r.conversations))
    const checked = await agent(checkTaxPrompt(`the group's ${ORD[y.year]} year (${spanPt(y)})`,
      `The verified conversations of this year:\n${JSON.stringify(convs)}`, prev.tax),
      { label: `check taxonomy year ${y.year}`, phase: 'Check taxonomy', schema: TAX_CHECKED })
    return { year: y.year, from: y.from, to: y.to, messages: y.messages, chunks: prev.ok, taxonomy: checked || prev.tax, taxonomy_unchecked: !checked }
  },
)
return { years: results.filter(Boolean) }
