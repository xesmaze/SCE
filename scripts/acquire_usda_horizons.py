
#!/usr/bin/env python3
"""Acquire USDA soil horizons using the SCE site manifest."""

import argparse
import csv
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest"

FIELDS = [
    "mukey", "muname", "cokey", "compname", "comppct_r",
    "chkey", "hzname", "hzdept_r", "hzdepb_r",
    "sandtotal_r", "silttotal_r", "claytotal_r",
    "dbthirdbar_r", "wthirdbar_r", "wfifteenbar_r",
    "om_r", "ph1to1h2o_r", "ksat_r",
]


def query(sql):
    body = urlencode({
        "query": sql,
        "format": "JSON+COLUMNNAME",
    }).encode()

    request = Request(
        API,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "SCE-v2-soil/0.2",
        },
    )

    with urlopen(request, timeout=90) as response:
        payload = json.load(response)

    table = payload.get("Table")

    if not isinstance(table, list) or not table:
        raise RuntimeError(
            f"Empty or invalid USDA response: {str(payload)[:500]}"
        )

    headers = [str(name).lower() for name in table[0]]

    return [
        dict(zip(headers, values))
        for values in table[1:]
    ]


def get_horizons(lat, lon):
    point = f"POINT({lon:.9f} {lat:.9f})"

    mapunits = query(
        "SELECT DISTINCT mukey FROM "
        "SDA_Get_Mukey_from_intersection_with_WktWgs84"
        f"('{point}')"
    )

    keys = sorted({
        str(row["mukey"])
        for row in mapunits
        if str(row.get("mukey", "")).isdigit()
    })

    if not keys:
        raise RuntimeError("No USDA soil map unit found.")

    values = ",".join(f"'{key}'" for key in keys)

    sql = f"""
    SELECT
      m.mukey, m.muname,
      c.cokey, c.compname, c.comppct_r,
      h.chkey, h.hzname, h.hzdept_r, h.hzdepb_r,
      h.sandtotal_r, h.silttotal_r, h.claytotal_r,
      h.dbthirdbar_r, h.wthirdbar_r, h.wfifteenbar_r,
      h.om_r, h.ph1to1h2o_r, h.ksat_r
    FROM mapunit m
    JOIN component c ON c.mukey = m.mukey
    LEFT JOIN chorizon h ON h.cokey = c.cokey
    WHERE m.mukey IN ({values})
    ORDER BY c.comppct_r DESC, c.cokey, h.hzdept_r
    """

    return keys, query(sql)


def valid_number(value):
    if value is None or str(value).strip() == "":
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def select_profile(rows):
    components = {}

    for row in rows:
        key = (str(row["mukey"]), str(row["cokey"]))
        components.setdefault(key, []).append(row)

    candidates = []

    for key, group in components.items():
        valid = [
            row for row in group
            if valid_number(row.get("hzdept_r")) is not None
            and valid_number(row.get("hzdepb_r")) is not None
            and valid_number(row["hzdepb_r"])
                > valid_number(row["hzdept_r"]) >= 0
        ]

        if valid:
            pct = valid_number(group[0].get("comppct_r")) or 0
            candidates.append((pct, key, group[0], valid))

    if not candidates:
        raise RuntimeError("No usable soil horizons found.")

    candidates.sort(key=lambda x: (-x[0], x[1]))

    _, _, component, horizons = candidates[0]

    horizons.sort(key=lambda r: float(r["hzdept_r"]))

    return component, horizons


def save_csv(path, rows, fields):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=fields, extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--site-manifest", required=True, type=Path
    )
    parser.add_argument(
        "--cache-dir", type=Path,
        default=Path("data/soil_cache")
    )
    parser.add_argument("--yes", action="store_true")

    args = parser.parse_args()

    config = json.loads(args.site_manifest.read_text())
    site = config["site"]

    lat = float(site["latitude"])
    lon = float(site["longitude"])

    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Invalid coordinates.")

    key = hashlib.sha256(
        f"{lat:.9f},{lon:.9f}".encode()
    ).hexdigest()[:16]

    output = args.cache_dir / key

    if (output / "soil_manifest.json").is_file():
        print("PASS: Cached soil profile:", output)
        return

    if output.exists():
        raise FileExistsError(
            f"Incomplete cache exists: {output}"
        )

    print("Site:", site["site_id"])
    print("Coordinates:", lat, lon)
    print("Source: USDA Soil Data Access")
    print("Download: map units, components and horizons only")

    if not args.yes:
        answer = input("Retrieve soil data? [y/N]: ")
        if answer.strip().lower() not in ("y", "yes"):
            print("Cancelled.")
            return

    keys, records = get_horizons(lat, lon)
    component, horizons = select_profile(records)

    normalized = []

    field_map = {
        "sand_pct": "sandtotal_r",
        "silt_pct": "silttotal_r",
        "clay_pct": "claytotal_r",
        "bulk_density_g_cm3": "dbthirdbar_r",
        "water_33kpa_pct": "wthirdbar_r",
        "water_1500kpa_pct": "wfifteenbar_r",
        "organic_matter_pct": "om_r",
        "ph": "ph1to1h2o_r",
        "ksat_um_s": "ksat_r",
    }

    for horizon in horizons:
        row = {
            "soil_id": (
                f"usda_{component['mukey']}_"
                f"{component['cokey']}"
            ),
            "top_cm": horizon["hzdept_r"],
            "bottom_cm": horizon["hzdepb_r"],
        }

        for name, source in field_map.items():
            row[name] = horizon.get(source)

        normalized.append(row)

    output.mkdir(parents=True)

    save_csv(
        output / "soil_layers.csv",
        normalized,
        list(normalized[0]),
    )

    save_csv(
        output / "all_components_horizons.csv",
        records,
        FIELDS,
    )

    manifest = {
        "site_id": site["site_id"],
        "latitude": lat,
        "longitude": lon,
        "source": "USDA Soil Data Access",
        "mukeys": keys,
        "selected_component": component["compname"],
        "component_percentage": component["comppct_r"],
        "horizon_count": len(horizons),
        "retrieved_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "apsim_ready": False,
        "apsim_modified": False,
    }

    (output / "soil_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )

    print("\nPASS: Soil horizon acquisition completed.")
    print(json.dumps(manifest, indent=2))
    print("Soil layers:", output / "soil_layers.csv")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
