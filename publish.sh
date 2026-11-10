#!/bin/bash
# Rebuild the public site into the gh-pages branch of this repo and commit it locally.
# Never pushes. Publishing = `git push origin gh-pages` (GitHub Pages serves that branch at
# arqueologiadigital.org/Telegram_logs_site/). Called by Telegram_logs/tools/daily.sh.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
WT=$(cd "$HERE/.." && pwd)/Telegram_logs_site-gh-pages     # git worktree of branch gh-pages
MEDIA_BASE=https://raw.githubusercontent.com/ArqueologiaDigital/Telegram_logs_media/main/
LEGACY_HTML="$HERE/../Telegram_logs-2018-private/formatted/html"

if [ ! -e "${WT:?}/.git" ]; then
  if git -C "$HERE" show-ref --verify --quiet refs/heads/gh-pages; then
    git -C "$HERE" worktree add -q "${WT:?}" gh-pages
  else
    git -C "$HERE" worktree add -q --orphan -b gh-pages "${WT:?}"
  fi
fi

# The search index (search_index.py) is rebuilt on Sundays, when missing, or with SEARCH=1;
# other days keep the previous one. Any rebuild rewrites ~3.6 MB of index files however few
# messages arrived (measured: research-scratch/tg-arqueologia/search_churn.py), which daily
# would add ~1.3 GB a year to the gh-pages history. Links in an older index stay valid,
# since pages never shift; only messages newer than the index are not found yet.
SEARCH_DIR="${WT:?}/formatted/html/pagefind"
KEEP="${WT:?}/.search-keep"
REBUILD_SEARCH=yes
rm -rf -- "${KEEP:?}"     # left over by a run that failed before restoring it
if [ -d "$SEARCH_DIR" ] && [ -f "${WT:?}/formatted/html/search.html" ] \
   && [ "$(date -u +%u)" != 7 ] && [ "${SEARCH:-0}" != 1 ]; then
  REBUILD_SEARCH=no
  mkdir "$KEEP"
  mv "$SEARCH_DIR" "$KEEP/"
fi

# Full rebuild: remove everything in the worktree except its .git file (and a kept search
# index), then build into it.
find "${WT:?}" -mindepth 1 -maxdepth 1 ! -name .git ! -name .search-keep -exec rm -rf -- {} +
python3 -I "$HERE/build.py" --out "${WT:?}" --media-base "$MEDIA_BASE"
if [ "$REBUILD_SEARCH" = yes ]; then
  "$HERE/../.venv/bin/python" -I "$HERE/search_index.py" --out "${WT:?}" --media-base "$MEDIA_BASE"
else
  mv "$KEEP/pagefind" "${WT:?}/formatted/html/"
  rmdir "$KEEP"
  # the search page itself is small and always rebuilt (python3: --page-only needs no pagefind)
  python3 -I "$HERE/search_index.py" --out "${WT:?}" --media-base "$MEDIA_BASE" --page-only
  echo "search index kept (rebuilt on Sundays, or run with SEARCH=1)"
fi
if [ -d "$LEGACY_HTML" ]; then
  python3 -I "$HERE/tests/compare_old_pages.py" "$LEGACY_HTML" "${WT:?}/formatted/html" >/dev/null \
    || { echo "2018 page compatibility test FAILED; not committing"; exit 1; }
fi

# Topic index pages (topics/render.py), only once topics/publish exists: the agent-written
# index is reviewed by a maintainer before it goes public.
if [ -f "$HERE/topics/publish" ]; then
  python3 -I "$HERE/topics/render.py" --out "${WT:?}" --media-base "$MEDIA_BASE"
fi

DATA_SHA=$(git -C "$HERE/../Telegram_logs" rev-parse --short HEAD)
SITE_SHA=$(git -C "$HERE" rev-parse --short HEAD)
cd "${WT:?}"
git add -A
if git diff --cached --quiet; then
  echo "site unchanged"
else
  git commit -q -m "Site build $(date -u +%F): data $DATA_SHA, generator $SITE_SHA" \
    -m "Built by Telegram_logs_site/publish.sh; do not edit by hand."
  echo "site committed on gh-pages: $(git rev-parse --short HEAD)"
fi
