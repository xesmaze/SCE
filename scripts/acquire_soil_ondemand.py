
#!/usr/bin/env python3
"""SCE v2 — on-demand USDA soil-profile acquisition.

Uses USDA Soil Data Access (SSURGO/STATSGO-derived tables).
Does NOT download the 10 m gNATSGO raster or modify APSIM.
Python standard library only.
"""

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SDA = "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest"

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
    }).encode("utf-8")

    request = Request(
        SDA,
        data=body,
        headers={
            "User-Agent": "SCE-v2-soil/0.1",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    with urlopen(request, timeout=120) as response:
        payload = json.load(response)

    table = payload.get("Table", [])
    if not table:
        raise ValueError(
            "USDA returned no soil data for this location."
        )

    headers = [str(x).lower() for x in table[0]]
    return [
        dict(zip(headers, values))
        for values in table[1:]
    ]


def obtain_profile(latitude, longitude):
    wkt = f"POINT({longitude:.10f} {latitude:.10f})"

    mapunits = query(f"""
        SELECT DISTINCT mukey
        FROM SDA_Get_Mukey_from_intersection_with_WktWgs84(
            '{wkt}'
        )
    """)

    keys = sorted({
        str(row["mukey"])
        for row in mapunits
        if str(row.get("mukey", "")).isdigit()
    })

    if not keys:
        raise ValueError("No mapped soil unit at site coordinates.")

    quoted = ",".join(f"'{key}'" for key in keys)

    records = query(f"""
        SELECT
            m.mukey, m.muname,
            c.cokey, c.compname, c.comppct_r,
            h.chkey, h.hzname,
            h.hzdept_r, h.hzdepb_r,
            h.sandtotal_r, h.silttotal_r, h.claytotal_r,
            h.dbthirdbar_r, h.wthirdbar_r, h.wfifteenbar_r,
            h.om_r, h.ph1to1h2o_r, h.ksat_r
        FROM mapunit m
        JOIN component c ON m.mukey = c.mukey
        JOIN chorizon h ON c.cokey = h.cokey
        WHERE m.mukey IN ({quoted})
        ORDER BY m.mukey, c.comppct_r DESC,
                 c.cokey, h.hzdept_r
    """)

    return keys, records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--site-manifest",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("data/soil_cache"),
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the interactive download confirmation.",
    )
    args = parser.parse_args()

    site_config = json.loads(
        args.site_manifest.read_text(encoding="utf-8")
    )
    site = site_config["site"]

    lat = float(site["latitude"])
    lon = float(site["longitude"])
    site_id = str(site["site_id"])

    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Invalid site coordinates.")

    key = hashlib.sha256(
        f"{lat:.8f},{lon:.8f}".encode()
    ).hexdigest()[:16]

    folder = args.cache_dir / key
    csv_path = folder / "soil_horizons.csv"
    manifest_path = folder / "soil_manifest.json"

    if csv_path.is_file() and manifest_path.is_file():
        print("Using cached USDA soil profile:")
        print(csv_path)
        return

    print(f"Site: {site_id}")
    print(f"Coordinates: {lat}, {lon}")
    print("Source: USDA Soil Data Access")
    print("Download: map-unit, component and horizon records only")
    print("No national or state raster will be downloaded.")

    if not args.yes:
        response = input(
            "\nRetrieve soil data from USDA? [y/N]: "
        ).strip().lower()

        if response not in ("y", "yes"):
            print("Acquisition cancelled.")
            return

    keys, records = obtain_profile(lat, lon)

    # Keep a representative component, but preserve all records.
    component_groups = {}

    for record in records:
        component_groups.setdefault(
            str(record["cokey"]), []
        ).append(record)

    def pct(rows):
        try:
            return float(rows[0].get("comppct_r") or 0)
        except (ValueError, TypeError):
            return 0.0

    ranked = sorted(
        component_groups.values(),
        key=pct,
        reverse=True,
    )

    selected = ranked[0]
    selected_key = str(selected[0]["cokey"])

    # Create a new cache entry without overwriting prior results.
    folder.mkdir(parents=True, exist_ok=True)

    with csv_path.open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(records)

    manifest = {
        "site_id": site_id,
        "latitude": lat,
        "longitude": lon,
        "source": "USDA Soil Data Access",
        "source_type": "point_survey_query",
        "not_a_gnatsgo_10m_raster": True,
        "service_url": SDA,
        "retrieved_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "mukeys": keys,
        "selected_component": {
            "cokey": selected_key,
            "name": selected[0]["compname"],
            "percentage": selected[0]["comppct_r"],
        },
        "selected_component_horizons": selected,
        "all_horizon_count": len(records),
        "apsim_ready": False,
        "apsim_model_modified": False,
    }

    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("\nPASS: USDA soil records retrieved.")
    print("Map units:", keys)
    print("Selected component:", selected[0]["compname"])
    print("Selected horizons:", len(selected))
    print("Cached CSV:", csv_path)
    print("Manifest:", manifest_path)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
