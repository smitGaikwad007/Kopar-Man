#!/usr/bin/env python3
"""
Import Kopargaon Bus Stand Timetable from data/timetable.csv

Usage:
    python scripts/import_timetable.py [--dir data] [--dry-run] [--db <url>]

The CSV must have columns:
    origin, destination, departure_time, data_source, source_doc, source_name

All records MUST carry data_source=OFFICIAL.

Idempotent: running the script multiple times will not create duplicate rows.
Failed imports roll back the entire transaction.
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.services.timetable import validate_timetable_rows, upsert_timetable_rows


def read_csv(filepath: str):
    if not os.path.exists(filepath):
        return []
    with open(filepath, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    parser = argparse.ArgumentParser(description="Import timetable data from CSV.")
    parser.add_argument("--dir", default="data", help="Directory containing timetable.csv")
    parser.add_argument("--dry-run", action="store_true", help="Validate only; do not write to DB")
    parser.add_argument("--db", default=settings.DATABASE_URL, help="Database URL")
    args = parser.parse_args()

    rows = read_csv(os.path.join(args.dir, "timetable.csv"))
    if not rows:
        print("ERROR: timetable.csv not found or empty.")
        sys.exit(1)

    print(f"Read {len(rows)} rows from timetable.csv")

    errors = validate_timetable_rows(rows)
    if errors:
        print("VALIDATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    if args.dry_run:
        print("Dry-run OK — validation passed. No changes written.")
        sys.exit(0)

    engine = create_engine(
        args.db,
        connect_args={"check_same_thread": False} if args.db.startswith("sqlite") else {},
    )
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        result = upsert_timetable_rows(session, rows)
        session.commit()
        print("IMPORT SUCCESSFUL")
        print(f"  Inserted: {result['inserted']}")
        print(f"  Updated:  {result['updated']}")
        print(f"  Total:    {result['total']}")
    except Exception as exc:
        session.rollback()
        print(f"IMPORT FAILED — rolled back. Error: {exc}")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
