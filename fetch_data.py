"""
fetch_data.py
=============
Downloads daily PM2.5 data for Sydney from the OpenAQ v3 API and writes it to
`sydney_pm25.csv`, the exact file the analysis notebook expects.

WHY THIS SCRIPT EXISTS
----------------------
The notebook (notebooks/sydney_air_quality_forecasting.ipynb) is the analysis.
This script is the *ingestion* step that feeds it. They are kept separate on
purpose: ingestion needs a network connection and an API key, whereas the
analysis should run anywhere, any time, from a static CSV. That separation is
standard practice and makes the whole project reproducible.

WHAT YOU NEED
-------------
1. A free OpenAQ API key:  https://explore.openaq.org/register
2. The SDK:                pip install openaq pandas
3. Set your key as an environment variable so it never gets committed to git:

       macOS / Linux:   export OPENAQ_API_KEY="your-key-here"
       Windows (PowerShell):  $env:OPENAQ_API_KEY="your-key-here"

HOW TO RUN
----------
    python fetch_data.py

Optional flags:
    python fetch_data.py --start 2019-01-01 --end 2021-12-31 --radius 30000

NOTES ON THE OpenAQ v3 API (important - v1/v2 were retired in Jan 2025)
----------------------------------------------------------------------
* A "location" is a monitoring station. Each station has one or more "sensors".
* A single sensor measures a single parameter (e.g. PM2.5). PM2.5 has
  parameters_id = 2.
* We request the `data="days"` rollup so OpenAQ returns daily averages computed
  server-side. Pulling raw hourly values for several years would be millions of
  rows; the daily rollup is the right resolution for a day-ahead forecast.
* Each daily record carries a `coverage` block telling us how many hours fed
  into that daily mean. We keep only days with >= 75% coverage (>= 18 of 24
  hours), the conventional completeness threshold for a representative daily
  average.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date, datetime

import pandas as pd

try:
    from openaq import OpenAQ
except ImportError:
    sys.exit(
        "The 'openaq' package is not installed.\n"
        "Install it with:  pip install openaq pandas"
    )

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
PM25_PARAMETER_ID = 2          # OpenAQ's parameter id for PM2.5
SYDNEY_LAT = -33.8688          # central Sydney
SYDNEY_LON = 151.2093
DEFAULT_RADIUS_M = 25_000      # 25 km search radius around the CBD
COVERAGE_THRESHOLD = 0.75      # keep daily averages built from >= 75% of hours
OUTPUT_PATH = "sydney_pm25.csv"


def get_client() -> OpenAQ:
    """Create an authenticated OpenAQ client from the OPENAQ_API_KEY env var."""
    api_key = os.environ.get("OPENAQ_API_KEY")
    if not api_key:
        sys.exit(
            "No API key found.\n"
            "Get a free key at https://explore.openaq.org/register, then set it:\n"
            '   export OPENAQ_API_KEY="your-key-here"   (macOS/Linux)\n'
            '   $env:OPENAQ_API_KEY="your-key-here"     (Windows PowerShell)'
        )
    return OpenAQ(api_key=api_key)


def find_sydney_pm25_sensors(client: OpenAQ, radius_m: int) -> list[dict]:
    """
    Find every PM2.5 sensor at stations within `radius_m` of central Sydney.

    Returns a list of dicts: {location, sensor_id, latitude, longitude}.
    """
    print(f"Searching for PM2.5 stations within {radius_m/1000:.0f} km of Sydney...")
    resp = client.locations.list(
        coordinates=(SYDNEY_LAT, SYDNEY_LON),
        radius=radius_m,
        parameters_id=PM25_PARAMETER_ID,
        limit=1000,
    )

    sensors: list[dict] = []
    for loc in resp.results:
        # Each location exposes a list of sensors; keep only PM2.5 ones.
        for sensor in (loc.sensors or []):
            param = getattr(sensor, "parameter", None)
            param_name = getattr(param, "name", "") if param else ""
            if param_name and param_name.lower() == "pm25":
                coords = getattr(loc, "coordinates", None)
                sensors.append(
                    {
                        "location": loc.name,
                        "sensor_id": sensor.id,
                        "latitude": getattr(coords, "latitude", None),
                        "longitude": getattr(coords, "longitude", None),
                    }
                )

    print(f"  Found {len(sensors)} PM2.5 sensor(s) across "
          f"{len({s['location'] for s in sensors})} station(s).")
    return sensors


def fetch_daily_for_sensor(
    client: OpenAQ,
    sensor_id: int,
    start: date,
    end: date,
) -> pd.DataFrame:
    """
    Pull daily-average PM2.5 for one sensor between start and end (inclusive),
    paginating until the API stops returning rows.
    """
    rows: list[dict] = []
    page = 1
    while True:
        resp = client.measurements.list(
            sensors_id=sensor_id,
            data="days",                # <-- server-side daily average rollup
            datetime_from=start.isoformat(),
            datetime_to=end.isoformat(),
            page=page,
            limit=1000,
        )
        results = resp.results or []
        if not results:
            break

        for m in results:
            # The daily timestamp lives in period.datetime_from (local time).
            period = getattr(m, "period", None)
            dt_from = getattr(period, "datetime_from", None) if period else None
            ts = getattr(dt_from, "local", None) or getattr(dt_from, "utc", None)

            # Coverage tells us how complete the daily average is.
            coverage = getattr(m, "coverage", None)
            pct = getattr(coverage, "percent_complete", None) if coverage else None

            rows.append(
                {
                    "date": ts,
                    "pm25": getattr(m, "value", None),
                    "percent_complete": pct,
                }
            )

        page += 1
        time.sleep(0.2)   # be polite to the API / stay under rate limits

    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Sydney PM2.5 from OpenAQ v3.")
    parser.add_argument("--start", default="2019-01-01", help="YYYY-MM-DD")
    parser.add_argument("--end", default="2021-12-31", help="YYYY-MM-DD")
    parser.add_argument("--radius", type=int, default=DEFAULT_RADIUS_M,
                        help="search radius in metres (default 25000)")
    args = parser.parse_args()

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()

    client = get_client()
    try:
        sensors = find_sydney_pm25_sensors(client, args.radius)
        if not sensors:
            sys.exit("No PM2.5 sensors found. Try a larger --radius.")

        frames: list[pd.DataFrame] = []
        for s in sensors:
            print(f"Fetching daily PM2.5 for '{s['location']}' "
                  f"(sensor {s['sensor_id']})...")
            df = fetch_daily_for_sensor(client, s["sensor_id"], start, end)
            if not df.empty:
                df["location"] = s["location"]
                frames.append(df)
                print(f"  -> {len(df)} daily records.")
            else:
                print("  -> no data in range.")
    finally:
        client.close()

    if not frames:
        sys.exit("No data returned for any sensor.")

    raw = pd.concat(frames, ignore_index=True)

    # --- Clean up ----------------------------------------------------------
    raw["date"] = pd.to_datetime(raw["date"], utc=True, errors="coerce").dt.tz_localize(None)
    raw = raw.dropna(subset=["date", "pm25"])

    # Keep only sufficiently complete daily averages.
    if raw["percent_complete"].notna().any():
        before = len(raw)
        raw = raw[raw["percent_complete"].fillna(0) >= COVERAGE_THRESHOLD * 100]
        print(f"Dropped {before - len(raw)} low-coverage days (<75%).")

    raw["date"] = raw["date"].dt.normalize()

    # Several stations cover Sydney; average them into one city-wide daily series.
    daily = (
        raw.groupby("date", as_index=False)["pm25"]
        .mean()
        .sort_values("date")
        .reset_index(drop=True)
    )
    daily["pm25"] = daily["pm25"].round(2)

    daily.to_csv(OUTPUT_PATH, index=False)
    print(f"\nWrote {len(daily)} daily records to {OUTPUT_PATH}")
    print(f"Date range: {daily['date'].min().date()} -> {daily['date'].max().date()}")
    print("\nDone. You can now run the analysis notebook.")


if __name__ == "__main__":
    main()
