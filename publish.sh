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

# Full rebuild: remove everything in the worktree except its .git file, then build into it.
find "${WT:?}" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf -- {} +
python3 -I "$HERE/build.py" --out "${WT:?}" --media-base "$MEDIA_BASE"
if [ -d "$LEGACY_HTML" ]; then
  python3 -I "$HERE/tests/compare_old_pages.py" "$LEGACY_HTML" "${WT:?}/formatted/html" >/dev/null \
    || { echo "2018 page compatibility test FAILED; not committing"; exit 1; }
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
