#!/usr/bin/env bash
# Weekly Monday run for citation-monitor — invoked by cron (see LAUNCH_CHECKLIST.md §4).
#
# Engine keys (GROQ_API_KEY, GEMINI_API_KEY) are sourced from ~/.citation-monitor-env
# so no secret ever lives in the crontab itself.
#
# The digest lands in  output/digest-<ISOweek>.md  and  output/digest-<ISOweek>.html
set -euo pipefail
cd "$(dirname "$0")/.."

ENV_FILE="${CITATION_MONITOR_ENV:-$HOME/.citation-monitor-env}"
if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  . "$ENV_FILE"
else
  echo "weekly.sh: $ENV_FILE not found — engine keys missing, run will degrade to demo mode" >&2
fi

mkdir -p output
PYTHONUNBUFFERED=1 python3 -m citation_monitor run --config "${1:-brand.yaml}"
