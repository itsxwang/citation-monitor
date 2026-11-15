#!/usr/bin/env bash
# Publish site/ (from main) to the gh-pages branch — orphan-branch pattern:
# clone -> orphan checkout -> copy site content (+ existing published digests) -> force push.
#
# Kept as a script so the Monday cron can refresh the public digest after each run
# (only publish digests meant to be public — customer digests are private pages/emails).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d -t citation-monitor-ghpages-XXXXXX)"
trap 'rm -rf "$WORK"' EXIT

git clone --quiet "$ROOT" "$WORK/clone"
cd "$WORK/clone"
git fetch --quiet origin gh-pages

# Preserve every digest page already published on gh-pages
mkdir "$WORK/digests"
git ls-tree --name-only origin/gh-pages | grep -E '^digest-.*\.html$' || true
while read -r f; do
  [ -n "$f" ] && git show "origin/gh-pages:$f" > "$WORK/digests/$f"
done < <(git ls-tree --name-only origin/gh-pages | grep -E '^digest-.*\.html$' || true)

git checkout --quiet --orphan gh-pages
git rm -rf --quiet . >/dev/null 2>&1 || true

cp -r "$ROOT/site/." .
cp "$WORK"/digests/*.html . 2>/dev/null || true
touch .nojekyll   # serve files as-is; skip Jekyll processing

git add -A
git commit -q -m "deploy: product landing page + og preview + robots/sitemap (site/ from main)"
git push --force --quiet origin gh-pages
echo "published gh-pages: $(git ls-tree --name-only HEAD | tr '\n' ' ')"
