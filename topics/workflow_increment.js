export const meta = {
  name: 'topic-index-increment',
  description: 'Topic index for the group year in progress: index its new messages, then add them to the cross-year topics they touch',
  phases: [
    { title: 'Segment', detail: 'one reader per transcript chunk: conversations with ids, titles, summaries, tags' },
    { title: 'Verify', detail: 'one skeptic per chunk re-reads the transcript and corrects or drops unsupported claims' },
    { title: 'Taxonomy', detail: 'the year so far: themes > subtopics > conversations, intro, highlights' },
    { title: 'Check taxonomy', detail: 'a skeptic checks every sentence of the year text against the verified conversations' },
    { title: 'Place', detail: 'stage "topics": the year\'s subtopics go into the cross-year topics' },
    { title: 'Write', detail: 'per touched topic: a note for the year and the smallest change to its summary' },
    { title: 'Check', detail: 'per touched topic: a skeptic checks the new text against the material' },
  ],
}

// Run in two stages, with the result saved and read by a person in between (topics/README.md,
// "Updating the year in progress"):
//   args.stage = 'year':   { stage, year, span, chunks: [{path, label, messages, first, last}] }
//     -> { chunks: [verified chunk], taxonomy, taxonomy_check }   (saved as data/<period>.json)
//   args.stage = 'topics': { stage, root, year, span, subtopics: [ids of the year's subtopics],
//                            topics: [{slug, title, scope}] }  (from crossyear.json)
//     -> { assign: [{subtopic, topic}], new_topics, texts: {slug: {addition, placement, note, corrections}} }
//   An existing topic's summary was reviewed by a person, so the agents never rewrite it: they
//   return only the sentences to add and where (topics/increment.py appends them); a new topic
//   gets a whole summary (placement "new").
// The segment, verify, taxonomy and check prompts are those of topics/workflow_years.js, with the
// year described as in progress and the gender rule added to the writing rules.

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
const PLACE = {
  type: 'object',
  properties: {
    new_topics: { type: 'array', items: { type: 'object', properties: {
      slug: { type: 'string' }, title: { type: 'string' }, scope: { type: 'string' } }, required: ['slug', 'title', 'scope'] } },
    assign: { type: 'array', items: { type: 'object', properties: {
      subtopic: { type: 'string' }, topic: { type: 'string', description: 'slug of an existing or new topic' } }, required: ['subtopic', 'topic'] } },
  },
  required: ['new_topics', 'assign'],
}
const TEXT = {
  type: 'object',
  properties: {
    addition: { type: 'string', description: 'pt-BR: the sentence(s) to add to the summary (the whole summary for a new topic); empty when nothing is worth adding' },
    placement: { type: 'string', enum: ['end-of-last-paragraph', 'new-paragraph', 'none', 'new'] },
    note: { type: 'string', description: 'one or two sentences: what happened on this topic in the year in progress' },
  },
  required: ['addition', 'placement', 'note'],
}
const TEXT_CHECKED = { type: 'object', properties: { ...TEXT.properties, corrections: { type: 'array', items: { type: 'string' } } },
  required: ['addition', 'placement', 'note', 'corrections'] }

const STYLE = `Writing rules (all text you produce):
- Brazilian Portuguese, neutral and factual, third person. No praise or hype ("incrível", "fascinante"), no filler.
- State only what the messages say. If you are unsure what something refers to, say less, never guess.
- Use people's names exactly as they appear in the transcript.
- Never copy phone numbers, e-mail addresses, street addresses or other personal data into your output.
- Describe what was discussed and done, not people's personalities or behaviour.
- Never assume anyone's gender, from a name or from anything else. Use feminine forms for L. (Acidx), Erin Pinheiro and Luciana Marques, who are women, and masculine forms for Jecel Assumpcao Jr. For everyone else, avoid words that mark their gender (pronouns "ele/ela", "dele/dela", gendered participles and adjectives about them): repeat the name or rephrase.`

const FORMAT = `Transcript format: one line per message:
  #<id> <YYYY-MM-DD HH:MM> <Name> [(↪#<id replied to>)] [markers]: <text>
Markers: [encaminhada de X], [foto], [vídeo], [áudio], [GIF], [figurinha], [documento: file], [link: page title], [enquete: question]. " ⏎ " is a line break inside a message. Times are Brasília time.`

const YEAR1_INTRO = 'No primeiro ano, de novembro de 2017 a outubro de 2018, o grupo funcionou como um grupo de estudos para preservar hardware histórico, com o resgate do Patinho Feio entre os principais projetos. Boa parte do trabalho aconteceu no acervo de computadores da Poli/USP: lá foram examinados os terminais e o PC-XT Nexus 2600 da Scopus, com explicações de DQ, ex-funcionário da empresa, e foram encontradas uma teletype e a leitora de fita perfurada Facit 4021. Com o MAME, o grupo emulou máquinas nacionais como o Sagitta, o Nexus 2600, o CP-500 e o CP-400, transcreveu para netlist os esquemáticos do Atari Gran Trak 10 e montou réplicas, entre elas a placa de decodificação de opcodes do Patinho Feio e o Golly Ghost. No mesmo período foram criados a organização ArqueologiaDigital no GitHub e o site arqueologiadigital.org, ROMs, manuais e imagens de disco foram publicados, e começaram os encontros e as oficinas no Garoa Hacker Clube.'

const ORD = ['', 'primeiro', 'segundo', 'terceiro', 'quarto', 'quinto', 'sexto', 'sétimo', 'oitavo', 'nono', 'décimo', 'décimo primeiro', 'décimo segundo']

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
5. The writing rules below, in particular the one on gender.
Drop a conversation that is mostly invented or trivial. Merge exact duplicates. Do not add new conversations unless you notice a clearly major one that is missing (then add it, checked the same way).
Also check the overview paragraph the same way.

Return the corrected index (same fields) and, in corrections, one line per change you made. An empty corrections list means you checked everything and found nothing wrong — only claim that if true.

${STYLE}

Index to check:
${JSON.stringify(seg)}`

const taxonomyPrompt = (ok, convs) => `You are designing part of the front page of the public archive of a Brazilian Telegram group about preserving historical computers and electronics ("Arqueologia Digital e Preservação Histórica por meio da Emulação de Dispositivos Eletrônicos"). The archive is organised by group year (each year runs November to October; the group began in November 2017). This page covers the group's ${ORD[args.year]} year, which is IN PROGRESS: so far it runs ${args.span}, ${convs.length} conversations. The page will be redone as the year goes on. Readers start from a summary of each year and drill down (progressive disclosure): year -> theme -> subtopic -> conversation -> message.

Below are the period overviews and all verified conversations of this year so far (id = the conversation's first message id). Organise them:
- intro: ONE paragraph summarising the year so far, for the top of the year's page and for the list of years on the front page. Start with "No ${ORD[args.year]} ano, iniciado em novembro de ${args.span.match(/\d{4}/)[0]}, ..." and make clear it covers only the first weeks; cover the main threads in a few dense sentences, shorter than a full year's summary. The first year's summary, as a style example only (do not copy its facts):
  "${YEAR1_INTRO}"
- themes: broad themes, ordered by importance to the group in this period (not alphabetically); for a few weeks, about 2 to 5. Each has a slug (lowercase ascii, hyphens), a title, a summary (1-3 sentences, grounded in the conversations it contains), and 1-5 subtopics.
- subtopics: specific (a machine, a project, a technique, an institution). Each has slug, title, summary (1-2 sentences) and conversation_ids, in chronological order.
- Every conversation must appear in at least one subtopic; one conversation may appear in two when it genuinely belongs to both. Do not drop any. If some conversations fit nothing else, make a final theme for them, but keep it small.
- highlights: the most important moments so far (first_id + why, one sentence), chronological; 0 to 4.
Base everything on the summaries given; do not add facts that are not in them.

${STYLE}

Period overviews:
${ok.map(r => `- ${r.overview}`).join('\n')}

Conversations:
${JSON.stringify(convs)}`

const checkTaxPrompt = (convs, tax) => `You are a skeptical fact-checker for the public archive of a Brazilian Telegram group about preserving historical computers. Another agent organised the verified conversations of the group's ${ORD[args.year]} year so far (${args.span}, a year in progress) into a year summary (intro), themes, subtopics and highlights. The conversation summaries have already been checked against the messages; the text written from them has not, and it can overstate, merge or misattribute (e.g. turn "conseguiu compilar o MAME no Windows" into "aprendeu a compilar o MAME"). Assume errors exist.

The verified conversations of this year so far:
${JSON.stringify(convs)}

Check EVERY sentence of intro, of each theme and subtopic summary, and of each highlight's "why" against the conversation summaries: correct or remove anything they do not support (outcomes stated more strongly than the summaries do, credit given to the wrong person, facts from no conversation). Check the writing rules below, in particular the one on gender. Also check: every conversation id in subtopics and highlights is one of these conversations; every conversation appears in at least one subtopic (add a missing one to the subtopic it fits best); slugs are lowercase ascii with hyphens and unique within the year; the intro says the year is in progress. Keep the structure and order unless something is broken; keep the intro's opening and style.

Return the corrected taxonomy (same fields) and, in corrections, one line per change. An empty list means you checked everything and found nothing wrong — only claim that if true.

${STYLE}

Taxonomy to check:
${JSON.stringify(tax)}`

const compact = convs => convs.map(c => ({ id: c.first_id, title: c.title, summary: c.summary, participants: c.participants, tags: c.tags, weight: c.weight }))

const CONTEXT = `The archive belongs to a Brazilian Telegram group about preserving historical computers and electronics ("Arqueologia Digital e Preservação Histórica por meio da Emulação de Dispositivos Eletrônicos"), active since November 2017. Its history is indexed by group year (year 1 = November 2017 to October 2018, ..., year ${args.year} = the year in progress, so far ${args.span}): each year has themes, each theme has subtopics, each subtopic lists conversations whose summaries were checked against the messages. Cross-year topics group the yearly subtopics by subject; each has a summary of all years and a note per year.`

if (args.stage === 'year') {
  const chunks = await pipeline(
    args.chunks,
    c => agent(segmentPrompt(c), { label: `segment ${c.label}`, phase: 'Segment', schema: SEGMENT }),
    (seg, c) => agent(verifyPrompt(c, seg), { label: `verify ${c.label}`, phase: 'Verify', schema: VERIFIED }),
  )
  const ok = chunks.filter(Boolean)
  if (ok.length !== args.chunks.length) log(`WARNING: ${args.chunks.length - ok.length} chunk(s) failed and are missing`)
  const convs = compact(ok.flatMap(r => r.conversations))
  log(`${convs.length} verified conversations, ${ok.reduce((n, r) => n + r.corrections.length, 0)} corrections`)
  phase('Taxonomy')
  const tax = await agent(taxonomyPrompt(ok, convs), { label: 'taxonomy', phase: 'Taxonomy', schema: TAXONOMY })
  phase('Check taxonomy')
  const checked = await agent(checkTaxPrompt(convs, tax), { label: 'check taxonomy', phase: 'Check taxonomy', schema: TAX_CHECKED })
  const { corrections, ...taxonomy } = checked || { ...tax, corrections: null }
  return { chunks: ok, taxonomy, taxonomy_check: { corrections, by: checked ? 'agent' : 'unchecked' } }
}

if (args.stage === 'topics') {
  const MAT = `python3 -I ${args.root}/topics/material.py`
  phase('Place')
  const place = await agent(`${CONTEXT}

The ${ORD[args.year]} year (in progress) has these subtopics: ${args.subtopics.join(', ')}. Run \`${MAT} --subtopics ${args.subtopics.join(',')}\` to read them, with their conversations. The existing cross-year topics (slug: title — scope):
${args.topics.map(t => `- ${t.slug}: ${t.title} — ${t.scope}`).join('\n')}

Assign every one of these subtopics to the existing topic it fits best (by slug); two only when it genuinely belongs to both. Only if one fits none, create a new topic for it (new_topics: slug lowercase ascii with hyphens, title, one-line scope in pt-BR) and assign it there. Copy ids exactly.

${STYLE}`, { label: 'place subtopics', phase: 'Place', schema: PLACE })
  const known = new Set(args.subtopics)
  const slugs = new Set([...args.topics.map(t => t.slug), ...place.new_topics.map(t => t.slug)])
  const assign = place.assign.filter(a => known.has(a.subtopic) && slugs.has(a.topic))
  const left = args.subtopics.filter(s => !assign.some(a => a.subtopic === s))
  if (left.length) log(`WARNING: not placed: ${left.join(', ')}`)
  const touched = [...new Set(assign.map(a => a.topic))].map(slug => {
    const t = args.topics.find(t => t.slug === slug)
    return { ...(t || place.new_topics.find(t => t.slug === slug)), isNew: !t, mine: assign.filter(a => a.topic === slug).map(a => a.subtopic) }
  })
  log(`${touched.length} topic(s) touched: ${touched.map(t => t.slug).join(', ')}`)
  const results = await pipeline(
    touched,
    t => agent(`${CONTEXT}

You are updating the page of one cross-year topic, "${t.title}" (${t.scope}), with what happened on it in the ${ORD[args.year]} year so far (${args.span}). Run \`${MAT} --subtopics ${t.mine.join(',')}\` to get that material and read all of it.

${t.isNew ? `This topic is new. Write in addition its whole summary, 1 or 2 short paragraphs, from the material; placement "new".` : `Run \`${MAT} --topic ${t.slug}\` to read the topic's current summary (all earlier years, already checked and reviewed by a person) and its notes per year. The current summary stays exactly as it is: do not return it. Return in addition only the one or two sentences to add about year ${args.year} so far, written to follow the current text (same style, chronological, saying it is the ${ORD[args.year]} year, in progress), and in placement where they go: "end-of-last-paragraph" or "new-paragraph". If the new material adds nothing worth a sentence at the level of this summary, return an empty addition and placement "none".`}
Write in note one or two sentences on what happened on this topic in year ${args.year} so far.

${STYLE}`, { label: `write ${t.slug}`, phase: 'Write', schema: TEXT }),
    (w, t) => agent(`${CONTEXT}

You are a skeptical fact-checker. Another agent wrote the text below for the cross-year topic "${t.title}" (${t.scope}), about what happened on it in the ${ORD[args.year]} year so far (${args.span}). Run \`${MAT} --subtopics ${t.mine.join(',')}\` to get the year's material${t.isNew ? '' : `, and \`${MAT} --topic ${t.slug}\` to see the summary the addition will follow (do not check or change that summary; only make sure the addition reads well after it and does not repeat it)`}. Check every sentence of addition and note against the material: correct or remove anything it does not support (outcomes stated more strongly than the material does, credit given to the wrong person, facts from no conversation). Check the writing rules below, in particular the one on gender.

Return the corrected text (same fields) and, in corrections, one line per change. An empty list means you checked everything and found nothing wrong — only claim that if true.

${STYLE}

Text to check:
${JSON.stringify(w)}`, { label: `check ${t.slug}`, phase: 'Check', schema: TEXT_CHECKED }),
  )
  const texts = {}
  touched.forEach((t, i) => { if (results[i]) texts[t.slug] = results[i] })
  return { assign, new_topics: place.new_topics, texts }
}

throw new Error(`unknown stage ${args.stage}`)
