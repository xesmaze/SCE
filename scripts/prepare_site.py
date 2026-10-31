
#!/usr/bin/env python3
"""
SCE v2.0 — Site configuration and environmental acquisition.

Creates a reusable site manifest containing:
- Site coordinates
- Trial period
- Weather source
- Soil source
- Previous crop and tillage
- Planting method

Optionally runs the existing Open-Meteo acquisition script.

gNATSGO acquisition is recorded but NOT yet automatically
downloaded. No APSIM files are modified.
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def ask(prompt, default):
    value = input(f"{prompt} [{default}]: ").strip()
    return value or str(default)


def choose(prompt, choices, default):
    while True:
        value = ask(
            f"{prompt} ({', '.join(choices)})",
            default
        ).lower()
        if value in choices:
            return value
        print("Invalid selection.")


def create_config(args):
    if args.interactive:
        site_id = ask("Site ID", "Illinois_Example")
        latitude = float(ask("Latitude", "40.763960462877"))
        longitude = float(ask("Longitude", "-89.7398359674323"))
        start_year = int(ask("Start year", "2001"))
        end_year = int(ask("End year", "2010"))

        weather = choose(
            "Weather source",
            ["era5", "station", "met"],
            "era5"
        )
        soil = choose(
            "Soil source",
            ["gnatsgo", "polaris", "csv"],
            "gnatsgo"
        )
        previous_crop = choose(
            "Previous crop",
            ["corn", "soybean", "wheat",
             "small_grain", "cover_crop", "fallow", "other"],
            "corn"
        )
        tillage = choose(
            "Tillage",
            ["conventional", "no_till", "strip_till"],
            "no_till"
        )
        planting = choose(
            "Planting method",
            ["drill", "planter"],
            "drill" if tillage == "no_till" else "planter"
        )
    else:
        site_id = args.site_id
        latitude = args.latitude
        longitude = args.longitude
        start_year = args.start_year
        end_year = args.end_year
        weather = args.weather
        soil = args.soil
        previous_crop = args.previous_crop
        tillage = args.tillage
        planting = args.planting

    if not (-90 <= latitude <= 90):
        raise ValueError("Latitude outside -90 to 90.")
    if not (-180 <= longitude <= 180):
        raise ValueError("Longitude outside -180 to 180.")
    if start_year > end_year:
        raise ValueError("Start year exceeds end year.")

    if any(c in site_id for c in "/\\") or site_id in ("", ".", ".."):
        raise ValueError("Invalid site ID.")

    if weather == "station" and not args.station_csv:
        raise ValueError(
            "--station-csv required for station weather."
        )
    if weather == "met" and not args.weather_met:
        raise ValueError(
            "--weather-met required for existing APSIM weather."
        )
    if soil == "csv" and not args.soil_csv:
        raise ValueError(
            "--soil-csv required for CSV soil source."
        )

    for supplied in [
        args.station_csv, args.weather_met, args.soil_csv
    ]:
        if supplied and not Path(supplied).is_file():
            raise FileNotFoundError(supplied)

    weather_input = (
        args.station_csv if weather == "station"
        else args.weather_met if weather == "met"
        else None
    )

    # The selected source defines only a default planting method.
    # The user can override it. No tillage or residue physics is
    # imposed by this configuration.
    config = {
        "schema_version": "sce-site-1.0",
        "site": {
            "site_id": site_id,
            "latitude": latitude,
            "longitude": longitude,
            "coordinate_system": "EPSG:4326",
        },
        "simulation": {
            "start_year": start_year,
            "end_year": end_year,
        },
        "environment": {
            "weather": {
                "source": weather,
                "model": "era5" if weather == "era5" else None,
                "input_file": (
                    str(Path(weather_input).resolve())
                    if weather_input else None
                ),
                "disclaimer": (
                    "ERA5 reanalysis estimates may differ from "
                    "field weather-station observations."
                ) if weather == "era5" else None,
            },
            "soil": {
                "source": soil,
                "input_file": (
                    str(Path(args.soil_csv).resolve())
                    if soil == "csv" else None
                ),
                "dataset": "USDA gNATSGO" if soil == "gnatsgo"
                           else "POLARIS" if soil == "polaris"
                           else "User CSV",
                "acquisition_status": "not_started",
            }
        },
        "management": {
            "previous_crop": previous_crop,
            "tillage": tillage,
            "planting_method": planting,
            "initialization_policy": (
                "Record choices as initialization metadata; "
                "do not infer residue quantities or soil nitrogen."
            ),
        },
        "created_utc": datetime.now().astimezone().isoformat(),
        "apsim_physiology_modified": False,
    }

    return config


def acquire_era5(config, output_dir):
    """Call the existing validated Open-Meteo script."""

    script = (
        Path(__file__).resolve().parent
        / "acquire_openmeteo_weather.py"
    )

    if not script.is_file():
        raise FileNotFoundError(
            f"Weather acquisition script not found: {script}"
        )

    site = config["site"]
    period = config["simulation"]

    command = [
        sys.executable,
        str(script),
        "--latitude", str(site["latitude"]),
        "--longitude", str(site["longitude"]),
        "--start-year", str(period["start_year"]),
        "--end-year", str(period["end_year"]),
        "--model", "era5",
        "--output-dir", str(output_dir / "weather"),
    ]

    print("\nRunning Open-Meteo acquisition...", flush=True)

    subprocess.run(command, check=True)

    weather_path = output_dir / "weather" / "weather.met"
    if not weather_path.is_file():
        raise RuntimeError(
            "Open-Meteo script completed without weather.met"
        )

    config["environment"]["weather"]["output_file"] = str(
        weather_path.resolve()
    )
    config["environment"]["weather"]["acquisition_status"] = (
        "complete"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Configure an SCE v2.0 site."
    )

    parser.add_argument(
        "--interactive", action="store_true"
    )
    parser.add_argument(
        "--site-id", default="Illinois_Example"
    )
    parser.add_argument(
        "--latitude", type=float, default=40.763960462877
    )
    parser.add_argument(
        "--longitude", type=float, default=-89.7398359674323
    )
    parser.add_argument(
        "--start-year", type=int, default=2001
    )
    parser.add_argument(
        "--end-year", type=int, default=2010
    )

    parser.add_argument(
        "--weather",
        choices=["era5", "station", "met"],
        default="era5"
    )
    parser.add_argument(
        "--soil",
        choices=["gnatsgo", "polaris", "csv"],
        default="gnatsgo"
    )

    parser.add_argument("--station-csv")
    parser.add_argument("--weather-met")
    parser.add_argument("--soil-csv")

    parser.add_argument(
        "--previous-crop",
        choices=["corn", "soybean", "wheat",
                 "small_grain", "cover_crop", "fallow", "other"],
        default="corn"
    )
    parser.add_argument(
        "--tillage",
        choices=["conventional", "no_till", "strip_till"],
        default="no_till"
    )
    parser.add_argument(
        "--planting",
        choices=["drill", "planter"],
        default="drill"
    )

    parser.add_argument(
        "--output-dir",
        default="site_configuration"
    )
    parser.add_argument(
        "--run-weather", action="store_true"
    )

    args = parser.parse_args()
    output_dir = Path(args.output_dir).resolve()

    if output_dir.exists():
        parser.error(
            "Output directory already exists; "
            "choose a new directory to preserve previous runs."
        )

    config = create_config(args)

    output_dir.mkdir(parents=True)

    # Write configuration before acquisition, so it is retained
    # even if an external weather request fails.
    manifest_path = output_dir / "site_manifest.json"
    manifest_path.write_text(
        json.dumps(config, indent=2) + "\n",
        encoding="utf-8"
    )

    if args.run_weather:
        if config["environment"]["weather"]["source"] != "era5":
            raise ValueError(
                "--run-weather currently supports ERA5 only."
            )
        acquire_era5(config, output_dir)

        manifest_path.write_text(
            json.dumps(config, indent=2) + "\n",
            encoding="utf-8"
        )

    print("\nSite configuration saved.")
    print(json.dumps({
        "site": config["site"],
        "weather_source": config["environment"]["weather"]["source"],
        "soil_source": config["environment"]["soil"]["source"],
        "manifest": str(manifest_path),
        "weather_file": config["environment"]["weather"].get(
            "output_file"
        ),
        "soil_acquired": False,
    }, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
