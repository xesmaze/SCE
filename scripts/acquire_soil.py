
#!/usr/bin/env python3
"""SCE v2: gNATSGO and user CSV soil-profile acquisition."""

import argparse
import csv
import hashlib
import json
import math
import sqlite3
from pathlib import Path

FIELDS = [
    "soil_id", "top_cm", "bottom_cm",
    "sand_pct", "silt_pct", "clay_pct",
    "bulk_density_g_cm3",
    "water_33kpa", "water_1500kpa",
    "organic_matter_pct", "ph", "ksat_um_s",
]

SOURCE = {
    "sand_pct": "sandtotal_r",
    "silt_pct": "silttotal_r",
    "clay_pct": "claytotal_r",
    "bulk_density_g_cm3": "dbthirdbar_r",
    "water_33kpa": "wthirdbar_r",
    "water_1500kpa": "wfifteenbar_r",
    "organic_matter_pct": "om_r",
    "ph": "ph1to1h2o_r",
    "ksat_um_s": "ksat_r",
}


def numeric(value):
    if value is None or str(value).strip() == "":
        return None
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"Nonfinite value: {value}")
    return number


def checksum(path):
    sha = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024), b""
        ):
            sha.update(chunk)
    return sha.hexdigest()


def validate(rows):
    if not rows:
        raise ValueError("No soil horizons available")

    rows.sort(key=lambda r: numeric(r["top_cm"]))
    warnings = []
    last_bottom = None

    for row in rows:
        top = numeric(row["top_cm"])
        bottom = numeric(row["bottom_cm"])

        if top is None or bottom is None:
            raise ValueError("Missing horizon depth")
        if top < 0 or bottom <= top:
            raise ValueError("Invalid horizon depths")

        if last_bottom is not None:
            if abs(top - last_bottom) > 0.00001:
                warnings.append(
                    f"Gap or overlap: {last_bottom}-{top} cm"
                )

        last_bottom = bottom

        for field in (
            "sand_pct", "silt_pct", "clay_pct",
            "organic_matter_pct",
            "water_33kpa", "water_1500kpa",
        ):
            value = numeric(row.get(field))
            if value is not None and not 0 <= value <= 100:
                raise ValueError(f"Invalid {field}: {value}")

        lower = numeric(row.get("water_1500kpa"))
        upper = numeric(row.get("water_33kpa"))

        if lower is not None and upper is not None:
            if lower > upper:
                raise ValueError(
                    "Water at 1500 kPa exceeds water at 33 kPa"
                )

        bd = numeric(row.get("bulk_density_g_cm3"))
        if bd is not None and not 0 < bd < 3:
            raise ValueError("Invalid bulk density")

        ph = numeric(row.get("ph"))
        if ph is not None and not 0 < ph <= 14:
            raise ValueError("Invalid pH")

    if numeric(rows[0]["top_cm"]) != 0:
        warnings.append("Profile does not start at 0 cm")

    return rows, warnings


def read_csv(path):
    with path.open(
        newline="", encoding="utf-8-sig"
    ) as handle:
        reader = csv.DictReader(handle)

        required = {"soil_id", "top_cm", "bottom_cm"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(
                "CSV requires soil_id, top_cm, bottom_cm"
            )

        return [
            {field: row.get(field) for field in FIELDS}
            for row in reader
        ]


def query_database(connection, sql, params=()):
    cursor = connection.execute(sql, params)
    columns = [item[0] for item in cursor.description]

    return [
        dict(zip(columns, record))
        for record in cursor.fetchall()
    ]


def get_gnatsgo(raster_path, gpkg_path, latitude, longitude):
    try:
        import rasterio
        from rasterio.warp import transform
    except ImportError as error:
        raise RuntimeError(
            "Install rasterio: python3 -m pip install rasterio"
        ) from error

    with rasterio.open(raster_path) as raster:
        if raster.crs is None:
            raise ValueError("Raster CRS is missing")

        xx, yy = transform(
            "EPSG:4326",
            raster.crs,
            [longitude],
            [latitude],
        )

        if not (
            raster.bounds.left <= xx[0] <= raster.bounds.right
            and raster.bounds.bottom <= yy[0] <= raster.bounds.top
        ):
            raise ValueError("Location outside raster extent")

        pixel = next(
            raster.sample(
                [(xx[0], yy[0])],
                masked=True,
            )
        )[0]

        if bool(getattr(pixel, "mask", False)):
            raise ValueError("No soil map unit at location")

        cell_value = int(pixel)

        raster_metadata = {
            "cell_value": cell_value,
            "crs": str(raster.crs),
            "resolution": list(raster.res),
        }

    # Open the GeoPackage read-only.
    database_uri = (
        f"file:{gpkg_path.resolve()}?mode=ro"
    )

    with sqlite3.connect(
        database_uri, uri=True
    ) as connection:

        for table in ("mapunit", "component", "chorizon"):
            columns = connection.execute(
                f'PRAGMA table_info("{table}")'
            ).fetchall()

            if not columns:
                raise ValueError(
                    f"GeoPackage missing table: {table}"
                )

        mapunits = query_database(
            connection,
            """
            SELECT mukey, muname
            FROM mapunit
            WHERE mukey = ?
            """,
            (str(cell_value),),
        )

        if len(mapunits) != 1:
            raise ValueError(
                "Raster cell does not correspond to a unique "
                "mapunit.mukey. Check whether this raster "
                "uses a separate map-unit lookup table."
            )

        mapunit = mapunits[0]
        mukey = str(mapunit["mukey"])

        components = query_database(
            connection,
            """
            SELECT cokey, compname, comppct_r
            FROM component
            WHERE mukey = ?
            """,
            (mukey,),
        )

        if not components:
            raise ValueError(
                f"No components found for mukey={mukey}"
            )

        candidates = []

        for component in components:
            horizons = query_database(
                connection,
                """
                SELECT *
                FROM chorizon
                WHERE cokey = ?
                ORDER BY hzdept_r
                """,
                (str(component["cokey"]),),
            )

            usable = [
                h for h in horizons
                if numeric(h.get("hzdept_r")) is not None
                and numeric(h.get("hzdepb_r")) is not None
            ]

            if usable:
                candidates.append((
                    numeric(component["comppct_r"]) or 0,
                    str(component["cokey"]),
                    component,
                    usable,
                ))

        if not candidates:
            raise ValueError(
                "No soil components with usable horizons"
            )

        candidates.sort(
            key=lambda item: (-item[0], item[1])
        )

        _, _, selected, horizons = candidates[0]

        soil_id = (
            f"gnatsgo_{mukey}_{selected['cokey']}"
        )

        rows = []

        for horizon in horizons:
            row = {
                "soil_id": soil_id,
                "top_cm": horizon["hzdept_r"],
                "bottom_cm": horizon["hzdepb_r"],
            }

            for output_field, source_field in SOURCE.items():
                row[output_field] = horizon.get(
                    source_field
                )

            rows.append(row)

        metadata = {
            "mapunit": mapunit,
            "components": components,
            "selected_component": selected,
            "raster": raster_metadata,
            "selection_policy": (
                "Highest reported component percentage "
                "with usable horizon depths"
            ),
        }

        return rows, metadata


def main():
    parser = argparse.ArgumentParser(
        description="SCE v2 soil acquisition"
    )

    parser.add_argument(
        "--source",
        required=True,
        choices=["gnatsgo", "polaris", "csv"],
    )
    parser.add_argument("--latitude", type=float)
    parser.add_argument("--longitude", type=float)
    parser.add_argument("--raster", type=Path)
    parser.add_argument("--gpkg", type=Path)
    parser.add_argument("--csv", type=Path)
    parser.add_argument(
        "--output-dir", required=True, type=Path
    )

    args = parser.parse_args()

    if args.output_dir.exists():
        parser.error(
            "Output directory already exists; "
            "refusing to overwrite"
        )

    if args.source == "polaris":
        parser.error(
            "POLARIS raster acquisition is not yet "
            "implemented. Pre-extracted profiles can "
            "be loaded with --source csv."
        )

    if args.source == "csv":
        if not args.csv or not args.csv.is_file():
            parser.error("Existing --csv file required")

        rows = read_csv(args.csv)
        details = {"input": str(args.csv.resolve())}
        inputs = [args.csv]

    else:
        if (
            not args.raster or not args.gpkg
            or not args.raster.is_file()
            or not args.gpkg.is_file()
        ):
            parser.error(
                "Existing --raster and --gpkg required"
            )

        if (
            args.latitude is None
            or args.longitude is None
            or not -90 <= args.latitude <= 90
            or not -180 <= args.longitude <= 180
        ):
            parser.error("Valid coordinates required")

        rows, details = get_gnatsgo(
            args.raster,
            args.gpkg,
            args.latitude,
            args.longitude,
        )

        inputs = [args.raster, args.gpkg]

    rows, warnings = validate(rows)

    missing = {
        field: sum(
            numeric(row.get(field)) is None
            for row in rows
        )
        for field in FIELDS[3:]
    }

    args.output_dir.mkdir(parents=True)

    output_csv = args.output_dir / "soil_layers.csv"

    with output_csv.open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle, fieldnames=FIELDS
        )
        writer.writeheader()
        writer.writerows(rows)

    manifest = {
        "source": args.source,
        "horizons": len(rows),
        "details": details,
        "warnings": warnings,
        "missing_fields": missing,
        "input_sha256": {
            str(path): checksum(path)
            for path in inputs
        },
        "output_sha256": checksum(output_csv),
        "apsim_model_modified": False,
        "apsim_ready": False,
        "note": (
            "SSURGO water-retention values are volumetric "
            "percent. Verify layer alignment and hydraulic "
            "bounds before converting to APSIM parameters."
        ),
    }

    (args.output_dir / "soil_manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str) + "\n"
    )

    print(json.dumps({
        "status": "PASS",
        "source": args.source,
        "soil_id": rows[0]["soil_id"],
        "horizon_count": len(rows),
        "missing_fields": missing,
        "warnings": warnings,
        "output_dir": str(args.output_dir),
    }, indent=2))


if __name__ == "__main__":
    main()
