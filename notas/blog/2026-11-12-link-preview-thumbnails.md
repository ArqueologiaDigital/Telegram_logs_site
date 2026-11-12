# Link-preview thumbnails in the chat pages

*2026-11-12*

The chat pages of the @arqueologiadigital archive now show the thumbnail of each link preview
(the frame of a YouTube video, a GitHub card, an article's picture), archived in the media
repository. The method is in the docstring of `Telegram_logs/tools/tg_media.py`.

## Telegram keeps preview photos for years

When someone posts a link, Telegram attaches a preview, often with a photo, and the message keeps
it. The archive had stored the preview's text but not its photo. Fetching the photos on
2026-11-12, at most 320 pixels wide:

| previews                                        | count |
|-------------------------------------------------|-------|
| with a photo in the archived message            | 2623  |
| photo fetched from Telegram                     | 2615  |
| not available any more (1 of them deleted)      | 8     |
| total size of the fetched photos                | 44 MB |

The oldest are from November 2017 and still came back. So the preview is a durable copy of what
a link looked like when it was shared, even when the page behind it has changed or gone; it is
now archived in the media repository rather than left to Telegram.

YouTube links whose message has no preview photo (46) got YouTube's own thumbnail instead; 6 of
those videos have been removed, and their thumbnails with them (HTTP 404). Of the 789 YouTube
links whose preview Telegram kept, the thumbnail survives whether or not the video does.

## A Telethon detail: progressive sizes cannot be asked for by object

Telethon's `download_media(photo, thumb=size)` silently downloads nothing when `size` is a
`PhotoSizeProgressive` object: its size selection only accepts `PhotoSize`, `PhotoCachedSize`,
`PhotoStrippedSize` and `VideoSize` objects (telethon 1.45.0, `_get_thumb`). Five previews whose
only size of at most 320 px was progressive came back empty, for example a Wikipedia preview
with sizes `m` (208 px) and progressive `x` (250 px). Asking by the size's type letter
(`thumb="x"`) works for every kind.
