
#!/usr/bin/env python3
"""Standalone APSIM soybean rotation/planting integration test."""

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path


def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from walk(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from walk(value)


def get_node(model, name, type_name):
    matches = [
        n for n in walk(model)
        if isinstance(n, dict)
        and n.get("Name") == name
        and type_name in str(n.get("$type", ""))
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected one {name} ({type_name}); found {len(matches)}"
        )
    return matches[0]


def set_parameters(manager, updates):
    parameters = manager.get("Parameters", [])

    for key, value in updates.items():
        matches = [
            p for p in parameters
            if p.get("Key") == key
        ]

        if len(matches) != 1:
            raise ValueError(
                f"Missing or duplicate parameter: {key}"
            )

        matches[0]["Value"] = str(value)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--template",
        default="template_models/Soy_Template_v2.0_APSIM2026.apsimx",
    )
    parser.add_argument(
        "--weather",
        default="template_models/z_12.met",
    )
    parser.add_argument(
        "--apsim",
        default=(
            "/Applications/APSIM2026.10.8138.0.app/"
            "Contents/Resources/bin/Models"
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="rotation_native_smoketest",
    )

    args = parser.parse_args()

    template = Path(args.template).resolve()
    weather = Path(args.weather).resolve()
    apsim = Path(args.apsim).resolve()
    output = Path(args.output_dir).resolve()

    for path in (template, weather, apsim):
        if not path.is_file():
            raise FileNotFoundError(path)

    if output.exists():
        raise FileExistsError(
            f"Output already exists: {output}"
        )

    model = json.loads(template.read_text())

    # Configure existing APSIM sowing manager.
    sowing = get_node(
        model, "Sowing", "Models.Manager"
    )

    sow_date = date(2001, 4, 12)

    set_parameters(sowing, {
        "SowDate": f"{sow_date.day}-{sow_date.strftime('%b').lower()}",
        "CultivarName": "mid000",
        "Population": "40",
        "RowSpacing": "190",
        "SowingDepth": "30",
    })

    # Disable inherited automatic management events.
    for name in (
        "Fertilise at sowing",
        "Tillage on a fixed date",
    ):
        manager = get_node(
            model, name, "Models.Manager"
        )
        manager["Enabled"] = False

    # Set simulation year.
    clock = get_node(
        model, "Clock", "Models.Clock"
    )

    for key, value in (
        ("Start", "2001-01-01"),
        ("End", "2001-12-31"),
    ):
        old = str(clock[key])
        clock[key] = (
            value + "T00:00:00"
            if "T" in old else value
        )

    # Point APSIM to the existing weather file.
    weather_nodes = [
        n for n in walk(model)
        if isinstance(n, dict)
        and "Models.Climate.Weather" in str(
            n.get("$type", "")
        )
        and "FileName" in n
    ]

    if not weather_nodes:
        raise ValueError(
            "Could not locate APSIM Weather node"
        )

    for node in weather_nodes:
        node["FileName"] = str(weather)

    # Stage a separate model; preserve the original.
    output.mkdir(parents=True)

    model_path = output / "IL_2001_mid000_drill.apsimx"
    model_path.write_text(
        json.dumps(model, indent=2) + "\n"
    )

    # Execute APSIM.
    command = [str(apsim), str(model_path)]

    print("Running APSIM:", model_path, flush=True)

    process = subprocess.run(
        command,
        cwd=output,
        capture_output=True,
        text=True,
    )

    (output / "apsim_stdout.log").write_text(
        process.stdout
    )
    (output / "apsim_stderr.log").write_text(
        process.stderr
    )

    if process.returncode != 0:
        raise RuntimeError(
            "APSIM execution failed. "
            "Check apsim_stderr.log"
        )

    databases = list(output.glob("*.db"))

    if len(databases) != 1:
        raise RuntimeError(
            f"Expected one APSIM database, found {len(databases)}"
        )

    # Verify the SQLite output.
    database = databases[0]

    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            'SELECT COUNT(*) FROM "Report"'
        ).fetchone()[0]

    results = {
        "status": "PASS" if rows > 0 else "FAIL",
        "apsim_returncode": process.returncode,
        "database": str(database),
        "report_rows": rows,
        "sowing_date_requested": "2001-04-12",
        "cultivar": "mid000",
        "population": 40,
        "row_spacing_mm": 190,
        "sowing_depth_mm": 30,
        "previous_crop_scenario": "corn",
        "tillage_scenario": "no-till",
        "planting_method_scenario": "drill",
        "fertilizer_manager_enabled": False,
        "tillage_manager_enabled": False,
    }

    result_file = (
        output / "rotation_integration_results.json"
    )

    result_file.write_text(
        json.dumps(results, indent=2)
    )

    print(json.dumps(results, indent=2))

    if rows == 0:
        raise RuntimeError("APSIM Report contains no data")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
