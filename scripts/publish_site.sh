#!/usr/bin/env bash
# Publish site/ (from main) to the gh-pages branch — orphan-branch pattern:
# fetch gh-pages -> orphan worktree -> copy site content (+ existing published digests)
# -> force push.
#
# Runs inside the main repo (so credentials/config apply). Kept as a script so the
# Monday cron can refresh the public digest after each run — only publish digests
# meant to be public; customer digests are private pages/emails.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

git remote get-url origin >/dev/null 2>&1 || { echo "publish_site.sh: no git remote 'origin'" >&2; exit 1; }
if ! git fetch --quiet origin gh-pages 2>/dev/null; then
  echo "no existing gh-pages on origin — starting a fresh one" >&2
fi

WORK="$(mktemp -d -t citation-monitor-ghpages-XXXXXX)"
cleanup() {
  cd "$ROOT"
  git worktree remove --force "$WORK/wt" 2>/dev/null || true
  git branch -D gh-pages-publish 2>/dev/null || true
  rm -rf "$WORK"
}
trap cleanup EXIT

# Preserve every digest page already published on gh-pages (live runs live there)
mkdir -p "$WORK/digests"
while read -r f; do
  [ -n "$f" ] && git show "origin/gh-pages:$f" > "$WORK/digests/$f"
done < <(git ls-tree --name-only origin/gh-pages 2>/dev/null | grep -E '^digest-.*\.html$' || true)

git worktree add --quiet --detach "$WORK/wt"
cd "$WORK/wt"
git checkout --quiet --orphan gh-pages-publish
git rm -rf --quiet . >/dev/null 2>&1 || true

cp -r "$ROOT/site/." .
cp "$WORK"/digests/*.html . 2>/dev/null || true
touch .nojekyll   # serve files as-is; skip Jekyll processing

git add -A
git commit -q -m "deploy: product landing page + og preview + robots/sitemap (site/ from main)"
git push --force --quiet origin gh-pages-publish:gh-pages
echo "published gh-pages:"
git ls-tree --name-only HEAD
