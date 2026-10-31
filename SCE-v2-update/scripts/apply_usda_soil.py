
#!/usr/bin/env python3
"""Stage an APSIM model with USDA soil properties."""

import argparse
import csv
import json
import math
import sys
from pathlib import Path


def nodes(obj):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from nodes(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from nodes(value)


def get_node(model, typename):
    found = [
        item for item in nodes(model)
        if isinstance(item.get("$type"), str)
        and item["$type"].split(",")[0].strip() == typename
    ]
    if len(found) != 1:
        raise ValueError(
            f"Expected one {typename}; found {len(found)}"
        )
    return found[0]


def number(value, name):
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(
            f"{name}: missing/non-numeric value"
        ) from None

    if not math.isfinite(result):
        raise ValueError(f"{name}: nonfinite value")

    return result


def read_soil(path):
    fields = [
        "top_cm", "bottom_cm",
        "sand_pct", "silt_pct", "clay_pct",
        "bulk_density_g_cm3",
        "water_33kpa_pct", "water_1500kpa_pct",
        "organic_matter_pct", "ph", "ksat_um_s",
    ]

    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = set(fields) - set(reader.fieldnames or [])

        if missing:
            raise ValueError(
                f"Missing CSV columns: {sorted(missing)}"
            )

        rows = [
            {key: number(row.get(key), key) for key in fields}
            for row in reader
        ]

    if not rows:
        raise ValueError("Soil CSV is empty")

    rows.sort(key=lambda row: row["top_cm"])

    previous_depth = 0

    for row in rows:
        top = row["top_cm"]
        bottom = row["bottom_cm"]

        if abs(top - previous_depth) > 1e-5 or bottom <= top:
            raise ValueError("Horizon gap, overlap or invalid depth")

        previous_depth = bottom

        texture = (
            row["sand_pct"]
            + row["silt_pct"]
            + row["clay_pct"]
        )

        if abs(texture - 100) > 2:
            raise ValueError("Texture does not sum to 100%")

        bd = row["bulk_density_g_cm3"]
        ll = row["water_1500kpa_pct"] / 100
        dul = row["water_33kpa_pct"] / 100
        sat = 1 - bd / 2.65

        if not (0 <= ll < dul < sat < 1):
            raise ValueError("Invalid LL15/DUL/SAT relationship")

        if not (
            0 < bd < 2.65
            and 0 < row["ph"] <= 14
            and 0 <= row["organic_matter_pct"] <= 100
            and row["ksat_um_s"] >= 0
        ):
            raise ValueError("Invalid soil properties")

    return rows


def intervals(thickness):
    top = 0
    for value in thickness:
        yield top, top + value
        top += value


def weighted(rows, top, bottom, field):
    total = 0

    for row in rows:
        overlap = max(
            0,
            min(bottom, row["bottom_cm"] * 10)
            - max(top, row["top_cm"] * 10),
        )
        total += overlap * row[field]

    return total / (bottom - top)


def check_arrays(component, thickness, fields, label):
    for field in fields:
        values = component.get(field)

        if isinstance(values, list):
            if len(values) != len(thickness):
                raise ValueError(
                    f"{label}.{field}: layer count mismatch"
                )


def check_thickness(component, thickness, label):
    values = component.get("Thickness")

    if not isinstance(values, list):
        raise ValueError(f"{label} missing Thickness")

    if len(values) != len(thickness):
        raise ValueError(f"{label}: layer count mismatch")

    if any(
        abs(number(a, label) - b) > 1e-5
        for a, b in zip(values, thickness)
    ):
        raise ValueError(
            f"{label}: layer boundaries differ from Physical"
        )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--template",
        type=Path,
        default=Path(
            "template_models/"
            "Soy_Template_v2.0_APSIM2026.apsimx"
        ),
    )
    parser.add_argument("--soil-csv", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--inspect-only", action="store_true")

    args = parser.parse_args()

    if not args.template.is_file():
        raise FileNotFoundError(args.template)

    rows = read_soil(args.soil_csv)
    model = json.loads(args.template.read_text())

    physical = get_node(model, "Models.Soils.Physical")
    organic = get_node(model, "Models.Soils.Organic")
    chemical = get_node(model, "Models.Soils.Chemical")

    thickness = [
        number(value, "Thickness")
        for value in physical.get("Thickness", [])
    ]

    if not thickness or any(t <= 0 for t in thickness):
        raise ValueError("Invalid APSIM layer thickness")

    model_depth = sum(thickness)
    soil_depth = rows[-1]["bottom_cm"] * 10
#
    if model_depth > soil_depth:
        extension_mm = model_depth - soil_depth

        if extension_mm > 300:
            raise ValueError(
                f"Required extrapolation is {extension_mm} mm, "
                "exceeding the 300 mm allowable limit."
            )

        print(
            f"WARNING: Extending deepest soil horizon by "
            f"{extension_mm:.0f} mm using its existing properties."
        )

        rows[-1] = dict(rows[-1])
        rows[-1]["bottom_cm"] = model_depth / 10

    # if model_depth > soil_depth:
    #     raise ValueError(
    #         f"APSIM profile ({model_depth} mm) exceeds "
    #         f"SSURGO profile ({soil_depth} mm). "
    #         "No extrapolation performed."
    #     )

    check_thickness(organic, thickness, "Organic")
    check_thickness(chemical, thickness, "Chemical")

    check_arrays(
        physical,
        thickness,
        [
            "BD", "AirDry", "LL15", "DUL", "SAT",
            "KS", "ParticleSizeSand",
            "ParticleSizeSilt", "ParticleSizeClay",
        ],
        "Physical",
    )

    check_arrays(
        organic, thickness,
        ["Carbon", "SoilCNRatio", "FBiom", "FInert", "FOM"],
        "Organic",
    )

    check_arrays(
        chemical, thickness, ["PH", "EC", "ESP"],
        "Chemical",
    )

    crop_nodes = [
        item for item in nodes(physical.get("Children", []))
        if isinstance(item.get("$type"), str)
        and "SoilCrop" in item["$type"]
    ]

    for crop in crop_nodes:
        check_arrays(
            crop, thickness,
            ["LL", "KL", "XF"],
            crop.get("Name", "SoilCrop"),
        )

    if args.inspect_only:
        print(json.dumps({
            "template_depth_mm": model_depth,
            "survey_depth_mm": soil_depth,
            "layers_mm": thickness,
            "crop_nodes": [
                item.get("Name") for item in crop_nodes
            ],
            "organic_keys": list(organic),
            "chemical_keys": list(chemical),
        }, indent=2))
        return

    if args.output.exists():
        raise FileExistsError(args.output)

    depths = list(intervals(thickness))

    def layer_values(field):
        return [
            weighted(rows, top, bottom, field)
            for top, bottom in depths
        ]

    bd = layer_values("bulk_density_g_cm3")
    ll15 = [
        value / 100
        for value in layer_values("water_1500kpa_pct")
    ]
    dul = [
        value / 100
        for value in layer_values("water_33kpa_pct")
    ]

    # Estimated porosity, particle density = 2.65 g/cm3.
    sat = [1 - value / 2.65 for value in bd]

    for lo, du, sa in zip(ll15, dul, sat):
        if not (0 <= lo < du < sa < 1):
            raise ValueError("Invalid converted hydraulic limits")
    # Soil-specific defaults for the new survey profile.
    # Crop lower limits are provisional estimates, not measurements.
    for crop in crop_nodes:
        crop["LL"] = list(ll15)

        # Existing uptake/exploration coefficients are retained.
        # They are template assumptions, not Fayette calibrations.
        print(
            f"INFO: {crop.get('Name')} LL initialized "
            "from survey-derived LL15."
        )
    # # Do not silently change inherited crop root-extraction limits.
    # for crop in crop_nodes:
    #     values = crop.get("LL", [])
    #     if isinstance(values, list):
    #         for index, (value, du) in enumerate(
    #             zip(values, dul), start=1
    #         ):
    #             if number(value, "SoilCrop.LL") > du:
    #                 raise ValueError(
    #                     f"{crop.get('Name')} layer {index}: "
    #                     "crop LL exceeds new DUL. "
    #                     "Explicit crop parameterization needed."
    #                 )

    updates = {
        "BD": bd,
        "AirDry": list(ll15),
        "LL15": ll15,
        "DUL": dul,
        "SAT": sat,
        "KS": [
            value * 86.4
            for value in layer_values("ksat_um_s")
        ],
        "ParticleSizeSand": layer_values("sand_pct"),
        "ParticleSizeSilt": layer_values("silt_pct"),
        "ParticleSizeClay": layer_values("clay_pct"),
    }

    for field, values in updates.items():
        if field not in physical:
            raise ValueError(f"Physical.{field} missing")
        physical[field] = values

    if "Carbon" not in organic or "PH" not in chemical:
        raise ValueError(
            "Organic.Carbon or Chemical.PH unavailable"
        )

    # Assumed organic carbon = 58% of organic matter.
    organic["Carbon"] = [
        value * 0.58
        for value in layer_values("organic_matter_pct")
    ]
    chemical["PH"] = layer_values("ph")
    # APSIM Water.InitialValues is authoritative at commencement;
    # InitialPAWmm by itself does not replace the original array.
    water = get_node(model, "Models.Soils.Water")
    check_thickness(water, thickness, "Water")
    existing = water.get("InitialValues")
    if not isinstance(existing, list) or len(existing) != len(thickness):
        raise ValueError("Water.InitialValues must match Physical.Thickness")
    water["InitialValues"] = list(dul)  # explicit 100% PAWC test scenario
    water["InitialPAWmm"] = sum(t * (d - l) for t, d, l in zip(thickness, dul, ll15))
    water["RelativeTo"] = "LL15"
    water["FilledFromTop"] = False
    if any(not (0 <= a <= l <= sw < sa) for a, l, sw, sa in zip(physical["AirDry"], ll15, water["InitialValues"], sat)):
        raise ValueError("Inconsistent initial hydraulic limits")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(model, indent=2) + "\n"
    )

    print(json.dumps({
        "status": "STAGED_NOT_EXECUTED",
        "model": str(args.output),
        "soil_depth_mm": model_depth,
        "layer_thickness_mm": thickness,
        "updated": [
            "BD", "LL15", "DUL", "SAT", "KS",
            "texture", "Organic.Carbon", "Chemical.PH",
            "Water.InitialValues", "Water.InitialPAWmm",
            "SoilCrop.LL", "AirDry",
        ],
        "preserved": [
            "mineral nitrogen",
            "crop KL and XF",
            "management",
            "APSIM equations",
        ],
    }, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("ERROR:", error, file=sys.stderr)
        sys.exit(1)
