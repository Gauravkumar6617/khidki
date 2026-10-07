"""Phase 0 data spike: which PM2.5 sensor near the centre has enough hourly data?

Run from backend/:  .venv/bin/python -m scripts.spike_data
"""
import gzip
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

from app.sources import openaq

OUTAGE = pd.Timestamp("2026-10-02 08:30", tz="UTC")  # OpenAQ's CPCB feed stopped here
WINDOWS = {
    "A": (OUTAGE - pd.Timedelta(days=90), OUTAGE),  # 90 days before the outage
    "B": (pd.Timestamp("2025-10-01", tz="UTC"), pd.Timestamp("2025-12-01", tz="UTC")),  # same season last year
}
MAX_MISSING = 20  # % of hours, in both windows
CPCB_DIR = Path(__file__).resolve().parents[1] / "data" / "cpcb"


def km(lat1, lon1, lat2, lon2):
    # equirectangular approximation; plenty for matching stations within a city
    return 111.2 * math.hypot(lat2 - lat1, (lon2 - lon1) * math.cos(math.radians(lat1)))


def feed_stations():
    """(name, lat, lon) of every station in the newest saved CPCB snapshot."""
    snaps = sorted(CPCB_DIR.glob("*.xml.gz"))
    if not snaps:
        return []
    root = ET.fromstring(gzip.decompress(snaps[-1].read_bytes()))
    return [
        (s.get("id"), float(s.get("latitude")), float(s.get("longitude")))
        for s in root.iter("Station")
        if s.get("latitude") and s.get("longitude")
    ]


def main():
    sensors = openaq.pm25_sensors()
    alive = sensors[pd.to_datetime(sensors.last_utc, utc=True) >= WINDOWS["B"][0]]
    print(f"{len(sensors)} PM2.5 sensors within 25 km, {len(alive)} with readings since Oct 2025")
    for w, (start, end) in WINDOWS.items():
        print(f"  window {w}: {start:%Y-%m-%d %H:%M} to {end:%Y-%m-%d %H:%M} UTC")

    feed = feed_stations()
    now = pd.Timestamp.now(tz="UTC")
    rows = []
    for s in alive.itertuples():
        row = {"sensor": s.sensor_id, "name": s.name[:30], "km": s.distance_km,
               "provider": s.provider, "monitor": s.is_monitor}
        for w, (start, end) in WINDOWS.items():
            h = openaq.hourly(s.sensor_id, f"{start:%Y-%m-%dT%H:%M:%SZ}", f"{end:%Y-%m-%dT%H:%M:%SZ}")
            # the API also returns the hour that straddles `start`, so trim to the window
            h = h[(h.time >= start) & (h.time < end)].dropna(subset=["pm25"])
            expected = (end - start) / pd.Timedelta(hours=1)
            row[f"{w}_miss%"] = round(100 * (1 - len(h) / expected))
            row[f"{w}_good%"] = round(100 * (h.coverage >= 75).sum() / expected)  # hours with >= 75% of readings
            row[f"{w}_mean"] = round(h.pm25.mean(), 1)
        row["stale_h"] = round((now - pd.Timestamp(s.last_utc)) / pd.Timedelta(hours=1))
        near = min(feed, key=lambda f: km(s.lat, s.lon, f[1], f[2]), default=None)
        row["cpcb_feed"] = near[0][:30] if near and km(s.lat, s.lon, near[1], near[2]) < 0.5 else "-"
        rows.append(row)

    t = pd.DataFrame(rows)
    print("\n" + t.to_string(index=False))
    ok = t[(t["A_miss%"] < MAX_MISSING) & (t["B_miss%"] < MAX_MISSING)]
    if ok.empty:
        print(f"\nNo sensor has < {MAX_MISSING}% missing in both windows. Stop and look for alternatives.")
    else:
        p = ok.iloc[0]  # rows are nearest first
        print(f"\nPick: {p['name']} (sensor {p['sensor']}), {p['km']} km")


if __name__ == "__main__":
    main()
