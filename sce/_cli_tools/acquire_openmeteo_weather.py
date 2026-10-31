
#!/usr/bin/env python3
"""
SCE v2.0 — Open-Meteo Historical Weather Acquisition

Downloads daily historical weather and generates an APSIM Next Gen .met file.

Outputs:
    weather.met
    openmeteo_response.json
    weather_manifest.json

Requires only the Python standard library.
Does not modify any existing APSIM models.
"""

import argparse
from datetime import date, timedelta
import hashlib
import json
import math
from pathlib import Path
import sys

from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://archive-api.open-meteo.com/v1/archive"

FIELDS = (
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "shortwave_radiation_sum",
)

EXPECTED_UNITS = {
    "temperature_2m_max": "°C",
    "temperature_2m_min": "°C",
    "precipitation_sum": "mm",
    "shortwave_radiation_sum": "MJ/m²",
}


def date_sequence(start, end):
    """Generate inclusive ISO-format daily dates."""
    days = (end - start).days + 1
    return [
        (start + timedelta(days=i)).isoformat()
        for i in range(days)
    ]


def validate_weather(payload, start, end):
    """Validate dates, variables, units and numerical values."""
    daily = payload.get("daily")
    units = payload.get("daily_units", {})

    if not isinstance(daily, dict):
        raise ValueError("API response has no daily weather data.")

    expected_dates = date_sequence(start, end)

    if daily.get("time") != expected_dates:
        raise ValueError(
            "Weather dates are missing, duplicated or out of order."
        )

    for variable in FIELDS:
        values = daily.get(variable)

        if not isinstance(values, list):
            raise ValueError(f"Missing variable: {variable}")

        if len(values) != len(expected_dates):
            raise ValueError(
                f"Incomplete data for {variable}"
            )

        if units.get(variable) != EXPECTED_UNITS[variable]:
            raise ValueError(
                f"Unexpected units for {variable}: "
                f"{units.get(variable)}"
            )

        for i, value in enumerate(values):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise ValueError(
                    f"Invalid {variable} on {expected_dates[i]}"
                )

            if variable in (
                "precipitation_sum",
                "shortwave_radiation_sum",
            ) and value < 0:
                raise ValueError(
                    f"Negative {variable} on {expected_dates[i]}"
                )

    for i, day in enumerate(expected_dates):
        if (
            daily["temperature_2m_min"][i]
            > daily["temperature_2m_max"][i]
        ):
            raise ValueError(
                f"Minimum temperature exceeds maximum on {day}"
            )

    return daily


def calculate_tav_amp(daily):
    """
    Calculate APSIM tav and amp from monthly air temperatures.

    tav: mean of twelve monthly mean temperatures
    amp: maximum monthly mean minus minimum monthly mean

    These values represent the requested years only.
    A longer historical baseline is recommended for production.
    """
    monthly = {m: [] for m in range(1, 13)}

    for day, tmin, tmax in zip(
        daily["time"],
        daily["temperature_2m_min"],
        daily["temperature_2m_max"],
    ):
        month = int(day[5:7])
        monthly[month].append((tmin + tmax) / 2)

    monthly_means = []

    for month in range(1, 13):
        values = monthly[month]

        if not values:
            raise ValueError(
                f"No observations for month {month}"
            )

        monthly_means.append(
            sum(values) / len(values)
        )

    tav = sum(monthly_means) / 12
    amp = max(monthly_means) - min(monthly_means)

    return tav, amp


def create_apsim_met(daily, latitude, longitude, model):
    """Convert Open-Meteo data to APSIM .met format."""

    tav, amp = calculate_tav_amp(daily)

    lines = [
        "[weather.met.weather]",
        f"! Open-Meteo historical weather: {model}",
        "! Reanalysis weather, not field observations",
        f"latitude = {latitude:.8f} (DECIMAL DEGREES)",
        f"longitude = {longitude:.8f} (DECIMAL DEGREES)",
        f"tav = {tav:.4f} (oC)",
        f"amp = {amp:.4f} (oC)",
        "year day radn maxt mint rain",
        "() () (MJ/m^2) (oC) (oC) (mm)",
    ]

    for i, day_string in enumerate(daily["time"]):
        day = date.fromisoformat(day_string)

        year = day.year
        doy = day.timetuple().tm_yday

        maxt = daily["temperature_2m_max"][i]
        mint = daily["temperature_2m_min"][i]
        rain = daily["precipitation_sum"][i]
        radn = daily["shortwave_radiation_sum"][i]

        lines.append(
            f"{year} {doy} "
            f"{radn:.4f} "
            f"{maxt:.3f} "
            f"{mint:.3f} "
            f"{rain:.3f}"
        )

    return "\n".join(lines) + "\n"


def acquire_weather(
    latitude,
    longitude,
    start_year,
    end_year,
    model,
    output_dir,
    input_json=None,
):
    """Download, validate and save historical weather."""

    start = date(start_year, 1, 1)
    end = date(end_year, 12, 31)

    output_dir = Path(output_dir)

    if output_dir.exists():
        raise FileExistsError(
            f"Output directory already exists: {output_dir}"
        )

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": ",".join(FIELDS),
        "timezone": "UTC",
        "temperature_unit": "celsius",
        "precipitation_unit": "mm",
        "models": model,
    }

    url = BASE_URL + "?" + urlencode(params)

    if input_json:
        raw = Path(input_json).read_bytes()
    else:
        print("Retrieving Open-Meteo historical weather...")
        print(f"Location: {latitude}, {longitude}")
        print(f"Years: {start_year}–{end_year}")
        print(f"Model: {model}")

        request = Request(
            url,
            headers={
                "User-Agent": "SCE-v2-weather/0.1"
            },
        )

        try:
            with urlopen(request, timeout=90) as response:
                raw = response.read()
        except (HTTPError, URLError, TimeoutError) as error:
            raise RuntimeError(
                f"Open-Meteo request failed: {error}"
            ) from error

    payload = json.loads(raw)

    if payload.get("error"):
        raise ValueError(
            "Open-Meteo API error: "
            + str(payload.get("reason", "Unknown error"))
        )

    daily = validate_weather(
        payload, start, end
    )

    met_text = create_apsim_met(
        daily, latitude, longitude, model
    )

    tav, amp = calculate_tav_amp(daily)

    manifest = {
        "provider": "Open-Meteo Historical Weather API",
        "dataset": model,
        "request_url": url,
        "requested_latitude": latitude,
        "requested_longitude": longitude,
        "returned_latitude": payload.get("latitude"),
        "returned_longitude": payload.get("longitude"),
        "returned_elevation_m": payload.get("elevation"),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "days": len(daily["time"]),
        "timezone": payload.get("timezone"),
        "units": {
            k: payload["daily_units"][k]
            for k in FIELDS
        },
        "tav_C": round(tav, 4),
        "amp_C": round(amp, 4),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "met_sha256": hashlib.sha256(
            met_text.encode("utf-8")
        ).hexdigest(),
        "note": (
            "TAV and AMP are calculated from the "
            "requested years, not a long-term baseline."
        ),
    }

    output_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    (output_dir / "openmeteo_response.json").write_bytes(raw)

    (output_dir / "weather.met").write_text(
        met_text,
        encoding="utf-8",
    )

    (output_dir / "weather_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("\nWeather acquisition complete.")

    print(
        json.dumps(
            {
                "status": "PASS",
                "weather_file": str(
                    output_dir / "weather.met"
                ),
                "days": len(daily["time"]),
                "model": model,
                "tav_C": round(tav, 4),
                "amp_C": round(amp, 4),
            },
            indent=2,
        )
    )


def main():
    parser = argparse.ArgumentParser(
        description="Acquire Open-Meteo weather for APSIM."
    )

    parser.add_argument(
        "--latitude",
        type=float,
        required=True,
    )

    parser.add_argument(
        "--longitude",
        type=float,
        required=True,
    )

    parser.add_argument(
        "--start-year",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--end-year",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--model",
        choices=("era5_land", "era5"),
        default="era5_land",
    )

    parser.add_argument(
        "--output-dir",
        required=True,
    )

    parser.add_argument(
        "--input-json",
        default=None,
        help="Use previously downloaded API JSON.",
    )

    args = parser.parse_args()

    end_year = args.end_year or args.start_year

    if not (
        -90 <= args.latitude <= 90
        and -180 <= args.longitude <= 180
    ):
        parser.error("Invalid coordinates.")

    min_year = 1950 if args.model == "era5_land" else 1940

    if (
        args.start_year < min_year
        or end_year < args.start_year
    ):
        parser.error("Invalid historical year range.")

    if (
        date(end_year, 12, 31)
        >= date.today() - timedelta(days=6)
        and not args.input_json
    ):
        parser.error(
            "Select completed historical years "
            "outside the reanalysis publication lag."
        )

    acquire_weather(
        latitude=args.latitude,
        longitude=args.longitude,
        start_year=args.start_year,
        end_year=end_year,
        model=args.model,
        output_dir=args.output_dir,
        input_json=args.input_json,
    )


if __name__ == "__main__":
    try:
        main()
    except (
        ValueError,
        RuntimeError,
        OSError,
    ) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
