"""OpenAQ v3: PM2.5 sensors near the centre, and their hourly values."""
import time

import httpx
import pandas as pd

from app.config import settings

client = httpx.Client(
    base_url="https://api.openaq.org/v3",
    headers={"X-API-Key": settings.openaq_api_key},
    timeout=30,
)


def _get(path, **params):
    time.sleep(1)  # stay under the 60 requests/min limit
    r = client.get(path, params=params)
    r.raise_for_status()
    return r.json()["results"]


def pm25_sensors():
    """Every PM2.5 sensor within 25 km (the API maximum) of the centre, nearest first."""
    locations = _get(
        "/locations",
        coordinates=f"{settings.center_lat},{settings.center_lon}",
        radius=25000,
        limit=1000,
    )
    rows = []
    for loc in locations:
        for s in loc["sensors"]:
            if s["parameter"]["name"] != "pm25":
                continue
            # first/last reading live on the sensor, not the location
            detail = _get(f"/sensors/{s['id']}")[0]
            rows.append({
                "sensor_id": s["id"],
                "location_id": loc["id"],
                "name": loc["name"],
                "provider": loc["provider"]["name"],
                "is_monitor": loc["isMonitor"],  # True = reference monitor, False = low-cost sensor
                "distance_km": round(loc["distance"] / 1000, 1),
                "lat": loc["coordinates"]["latitude"],
                "lon": loc["coordinates"]["longitude"],
                "first_utc": (detail["datetimeFirst"] or {}).get("utc"),
                "last_utc": (detail["datetimeLast"] or {}).get("utc"),
            })
    return pd.DataFrame(rows).sort_values("distance_km", ignore_index=True)


def hourly(sensor_id, start, end):
    """Hourly PM2.5 for one sensor between start and end (UTC).

    time = start of the hour. OpenAQ hours run :30 to :30 UTC, i.e. :00 to :00 IST.
    coverage = % of the hour's 15-minute readings that arrived.
    """
    rows, page = [], 1
    while True:
        batch = _get(
            f"/sensors/{sensor_id}/hours",
            datetime_from=start, datetime_to=end, limit=1000, page=page,
        )
        rows += [
            {
                "time": r["period"]["datetimeFrom"]["utc"],
                "pm25": r["value"],
                "coverage": r["coverage"]["percentCoverage"],
            }
            for r in batch
        ]
        if len(batch) < 1000:
            break
        page += 1
    df = pd.DataFrame(rows, columns=["time", "pm25", "coverage"])
    df["time"] = pd.to_datetime(df["time"], utc=True)
    return df.sort_values("time", ignore_index=True)


if __name__ == "__main__":
    print(pm25_sensors().drop(columns=["lat", "lon"]).to_string(index=False))
    # Lalbagh's active sensor; 3 months is > 1000 hours, so paging gets exercised
    h = hourly(12235522, "2026-07-01", "2026-10-03")
    assert h.time.is_unique, "pages overlapped"
    print(f"\n{len(h)} hours, {h.pm25.isna().sum()} null\n{h.tail(3).to_string(index=False)}")
