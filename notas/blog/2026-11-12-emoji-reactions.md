# Emoji reactions in the chat pages

*2026-11-12*

The chat pages of the @arqueologiadigital archive now show the emoji reactions under each
message, one chip per emoji with its count ("👍 3"). Hovering a chip lists who reacted.

## They were already in the archive

The daily sync stores each message as Telethon's `Message.to_dict()`, and that includes
`reactions`, so no new fetch was needed. The archive data up to message #42296 holds:

| what                                             | count |
|--------------------------------------------------|-------|
| messages                                         | 40994 |
| messages with at least one reaction              | 3174  |
| distinct emoji used (one of them a custom emoji) | 45    |
| 👍 reactions, the most used                      | 1506  |
| ❤ reactions, the second                          | 1466  |

Telegram introduced reactions at the end of December 2021, and the first one here is from
2021-12-31. Two messages from earlier in 2021 got theirs later, in 2022 and 2023: a reaction is
filed under its message's date, not its own. Messages with reactions since then: 534 in 2022,
495 in 2023, 667 in 2024, 683 in 2025 and 792 so far in 2026.

## Telegram does not list your own reaction

Each emoji is a chip, so a message with 👍 and 🔥 has two. To name who reacted, Telegram gives a
`recent_reactions` list. Comparing that list with the counts:

| chips                                                          | count |
|----------------------------------------------------------------|-------|
| every reactor named (counting the archiving account, below)    | 3266  |
| some reactors named (Telegram returns only the latest few)     | 142   |
| no reactor named                                               | 17    |
| chosen by the archiving account                                | 289   |

The archiving account's own reaction never appears in `recent_reactions`: all 289 chips it chose
lack it. Telegram marks those with `chosen_order` instead. So the page builder names that
reaction itself, using the sender of the messages Telegram marks as "out" (sent by the
archiving account). Without this, Felipe's name would be missing from every reaction he made.

## Limits

- Reactions are as of the last sync that scanned the message. The daily sync rescans the last
  30 days, so a reaction added later to an older message appears only after a full sync
  (`tools/tg_sync.py sync --full`; the last one ran on 2026-11-09).
- The names are in a `title` tooltip, which touch screens do not show.
- The one custom emoji is a sticker we do not download; it shows as ✱.

## Reproduce

    cd Telegram_logs_site
    python3 -I tests/reaction_counts.py ../Telegram_logs

The renderer is `render_reactions` in `build.py`.
