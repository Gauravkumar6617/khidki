#!/bin/sh
# Hourly raw snapshot of CPCB's live CAAQMS feed, run by cron.
# Kept raw on purpose: live readings can't be fetched later, and the
# field meanings (Min/Max/Avg, Hourly_sub_index) aren't confirmed yet.
set -eu
dir="$(dirname "$0")/../data/cpcb"
mkdir -p "$dir"
f="$dir/$(date -u +%Y%m%dT%H%MZ).xml"
curl -fsS -m 60 -o "$f" https://airquality.cpcb.gov.in/caaqms/rss_feed || { rm -f "$f"; exit 1; }
gzip "$f"
