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
