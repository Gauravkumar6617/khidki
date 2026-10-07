# Agent log

Decisions, surprises and breakages, newest at the bottom. Times are IST.
Feeds the write-up.

## Wed Oct 7 — Phase 0: data spike

**Laptop check (the agent ran it instead of asking):** 7.5 GB RAM (about 3.4 GB free with normal use), Intel Iris Xe, no CUDA GPU, Python 3.12.3, Node 24. Docker, Ollama, Tiger CLI, gh and uv are not installed.

**Model picks, from that check:**
- Gemma: `gemma4:e2b-it-qat` (4.3 GB). e4b needs at least 6.1 GB just for its weights (Ollama tags page), so it doesn't fit. Use a small `num_ctx` and `keep_alive: 0`, so Gemma unloads as soon as the message is written. Gemma and TabPFN never run at the same time.
- TabPFN: CPU only, `ModelVersion.V3_5_FAST`, with the training table kept well under 5,000 rows. The Prior Labs docs page lists `V3_5`, `V3_5_FAST`, `V3` and `V2_6`. Gaurav pointed out that the TabPFN README also has `ModelVersion.V2` (TabPFN-2), which is for the stretch comparison only.
- No Docker, so the local TimescaleDB fallback isn't ready. Tiger Cloud is the only database path for now.

**Simplifications (keep the stack small):**
- `requirements.txt` instead of `pyproject.toml`. This is an app, not a package, and a flat `app/` + `scripts/` layout triggers setuptools' "multiple top-level packages" error.
- No disk cache for API responses. One spike run is about 30 OpenAQ calls against a 2,000/hour limit, and `sleep(1)` between calls keeps us under 60/min. From Phase 1 on, the database is the cache: ingest only fetches hours after the newest one stored.
- The fetch code lives in `app/sources/` from day one, so the spike and Phase 1 ingest share it instead of keeping two copies.

**Gaurav's decisions:**
- Centre the station search on Gaurav's own area, not the city centre, and prefer the closest station that passes the checks. The exact coordinates go only in the local `.env`; `.env.example` (public) keeps Lucknow city centre.
- Public GitHub repo from the start, and `.env` must be gitignored before the first push. Verified: `git check-ignore -v .env` matches `.gitignore:1`.
- Entire: skipped tonight.
- The laptop may be asleep at 5 AM, so the daily job runs the **night before**, and ntfy's scheduled delivery sends the push at wake-up time (check the ntfy docs in Phase 3). That same evening issue time is used when building the training rows and the backtest, so the backtest matches what really runs. The exact hour is still open; pick it in Phase 2.
- Saturday add-on, only if Phases 0–3 are done: an ESP32 "khidki box" by the door (ESP32, 0.96" I2C OLED, HC-SR501 PIR, optional IR sensor for wave-to-check-in). It replaces the web page as the demo. Effect on Phase 3: also publish the window as small JSON to a second ntfy topic that the ESP32 polls over Wi-Fi. The box saves the last window it received, so a reboot or an expired ntfy message doesn't blank the screen. MicroPython, and the wiring gets explained before any code.
- Public repo: https://github.com/Gauravkumar6617/khidki. Commits use the GitHub no-reply email so no personal address ends up in the public history. Checked with `git ls-files` before the first push: `.env` is not tracked.

**Surprise: OpenAQ's CPCB feed is down across India (found while checking the API for step 3).**
- All 10 OpenAQ locations within 25 km of Lucknow are CPCB/UPPCB stations. Every active one has `datetimeLast` = 2026-10-02 08:30 UTC.
- The hourly data really does stop there. Sensor 12235522 (Lalbagh) has 171 of about 178 hours from Sep 25 to Oct 2, then nothing.
- Delhi (46 CPCB locations), Kanpur and Mumbai stop at exactly the same minute. Sources that don't come from CPCB are current: AirGradient in Delhi, AirNow in Mumbai. So this is a break in OpenAQ's CPCB ingestion, not a problem with any one station or city, and switching city doesn't help.
- An open-source project (github.com/antutroll27/delta-climate-research PR #34) says the relay has been "down since 2026-09-24". Our Lucknow data continues until Oct 2, so it may have been patchy first and then stopped completely.
- CPCB's own public feed, `https://airquality.cpcb.gov.in/caaqms/rss_feed` (XML, no key), is live: all 6 Lucknow stations show lastupdate 07-10-2026 23:00. Per station it gives PM2.5 `Min`/`Max`/`Avg` plus `Hourly_sub_index`, and the coordinates match OpenAQ's (e.g. Lalbagh 26.8458805, 80.9365541). It is a current snapshot with no history, and the exact meaning of the fields (averaging window, sub-index or concentration) still needs checking against CPCB.

**OpenAQ API facts, checked against real responses:**
- `coordinates=lat,lon`, `radius` in metres with a maximum of 25,000. The rate-limit headers say 60/min.
- `/v3/sensors/{id}/hours` returns `value`, `period.datetimeFrom.utc` and `coverage.percentCoverage`. Hours start at :30 UTC, which is :00 IST.
- Locations can have an old PM2.5 sensor with no recent data (e.g. 15143) next to a new active one (122355xx), and the same site can appear more than once (Central School: 2463, 5657, 3409318). So the spike checks every PM2.5 sensor and doesn't trust location metadata.

**Decisions after the outage (Gaurav):**
- Don't wait for OpenAQ. Train on OpenAQ history up to Oct 2 **plus Oct–Nov 2025** (same season last year). The 90 days before the outage are mostly monsoon and the cleanest air of the year, but we deploy in October.
- Train the model the way it will run. While station readings are stale, the live forecast uses a model trained **without** the station features, not one trained with them and then fed blanks. The with/without comparison stays in the backtest and the post.
- Weather for Oct–Nov 2025 comes from Open-Meteo's **Historical Forecast API**, because the regular forecast endpoint only reaches back about 3 months.

**Verified (one request each, at Lucknow city centre):**
- Air Quality API, `domains=cams_global`, `start_date=2025-10-01`, `end_date=2025-11-30`: 1,464 hourly rows with no nulls, times in GMT by default. CAMS PM2.5 averages 55.4 µg/m³ in October and 84.3 in November, so the seasonal rise shows up even in the model.
- Historical Forecast API (`historical-forecast-api.open-meteo.com/v1/forecast`), same dates: all six fields, `boundary_layer_height` included, 1,464 rows with no nulls.

**The CPCB live feed has been logged raw every hour since Oct 7, 23:20 IST.** `backend/scripts/log_cpcb.sh` runs from cron at :20 past each hour and saves gzipped XML (about 49 KB per snapshot) to `backend/data/cpcb/`, which is gitignored. Errors go to `cron.log` there. Why: live readings can't be fetched later, and we need them to check the Saturday field test. Known gap: cron doesn't run while the laptop is asleep, and it doesn't catch up missed hours afterwards.

**Step 3, `app/sources/openaq.py`.** `python -m app.sources.openaq` runs it in about 33 s (mostly the polite 1 s sleeps).
- Within 25 km of Lucknow centre: 15 PM2.5 sensors at 10 locations. All are reference monitors (`isMonitor=True`) from CPCB or UPPCB. There are no low-cost sensors on OpenAQ near the centre (to recheck from Gaurav's own centre).
- The 6 active sensors (122355xx–122366xx) all start on **2025-02-18** and stop on 2026-10-02 08:30 UTC. The old ids at the same locations went dead around Oct 2022. So Oct–Nov 2025 history exists, but only under the new ids.
- Lalbagh 12235522, Jul 1–Oct 2: 1,971 hours over 2 pages, unique timestamps, no null values. The paging check passed.

**Step 4, `scripts/spike_data.py`, run from the Lucknow city-centre default.** Took about 2 minutes. To re-run once Gaurav's own centre is in `.env`.
```
  sensor                           name  km provider  monitor  A_miss%  A_good%  A_mean  B_miss%  B_good%  B_mean  stale_h                      cpcb_feed
12235522        Lalbagh, Lucknow - CPCB 1.0     CPCB     True       12       75    27.3        6       82    81.3      130        Lalbagh, Lucknow - CPCB
12235478 Central School, Lucknow - CPCB 4.2     CPCB     True        6       80    25.9        4       84    75.6      130                              -
12235574 Talkatora District Industries  5.6     CPCB     True        6       87    26.9        5       83    83.5      130 Talkatora District Industries 
12235985   Gomti Nagar, Lucknow - UPPCB 6.3     CPCB     True       11       81    32.5        6       86    66.3      130   Gomti Nagar, Lucknow - UPPCB
12236630 Kukrail Picnic Spot-1, Lucknow 7.8     CPCB     True       16       73    21.6        6       85    44.1      130 Kukrail Picnic Spot-1, Lucknow
12236621 B R Ambedkar University, Luckn 9.1     CPCB     True       20       66    22.1        6       85    63.4      130 B R Ambedkar University, Luckn
```
Window A = the 90 days before the outage (2026-07-04 to 10-02). Window B = 2025-10-01 to 12-01. `good%` = hours where at least 75% of the 15-minute readings arrived.
- **Pick: Lalbagh (sensor 12235522), 1.0 km from the centre.** 12% of hours missing in A and 6% in B, and the station is also in CPCB's live feed, so the Saturday check is possible. 5 of the 6 live sensors pass the "under 20% missing in both windows" rule; B R Ambedkar University sits exactly at 20% in A and fails.
- **The season gap is real:** mean PM2.5 is 22–33 µg/m³ in window A (monsoon) and 44–84 in window B (Oct–Nov 2025). Lalbagh goes from 27 to 81, three times higher. Training only on the last 90 days would have learned the wrong season.
- OpenAQ's "Central School" (12235478) is **not** in the CPCB feed within 0.5 km. The feed's "Kendriya Vidyalaya" has different coordinates, so the name guess was wrong.
- `good%` is 66–87%, so some hours we have are based on only part of their 15-minute readings. Pick a coverage cutoff when building the features in Phase 2.
