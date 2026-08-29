import argparse
import csv
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add app to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.core.config import settings
from app.services.ingestion import TransportIngestionService

def read_csv(filepath):
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)

def validate_and_import(data_dir, db_url, dry_run=False):
    buses_data = read_csv(os.path.join(data_dir, 'buses.csv'))
    routes_data = read_csv(os.path.join(data_dir, 'routes.csv'))
    route_stops_data = read_csv(os.path.join(data_dir, 'route_stops.csv'))
    schedules_data = read_csv(os.path.join(data_dir, 'schedules.csv'))
    parcel_cap_data = read_csv(os.path.join(data_dir, 'parcel_capacity.csv'))

    errors = TransportIngestionService.validate_data(
        buses_data=buses_data,
        routes_data=routes_data,
        route_stops_data=route_stops_data,
        schedules_data=schedules_data,
        parcel_cap_data=parcel_cap_data
    )

    if errors:
        print("VALIDATION FAILED:")
        for err in errors:
            print(f" - {err}")
        return False

    if dry_run:
        print("Dry run successful. Validation passed.")
        return True
        
    engine = create_engine(db_url, connect_args={"check_same_thread": False} if db_url.startswith("sqlite") else {})
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        result = TransportIngestionService.upsert_data(
            db=session,
            buses_data=buses_data,
            routes_data=routes_data,
            route_stops_data=route_stops_data,
            schedules_data=schedules_data,
            parcel_cap_data=parcel_cap_data
        )
        session.commit()
        
        print("IMPORT SUCCESSFUL")
        print("Records loaded:")
        for k, v in result["counts"].items():
            print(f"{k.capitalize()}: {v}")
        
        print("\nData sources:")
        for source, count in result["source_counts"].items():
            print(f"{source}: {count}")

        return True

    except Exception as e:
        session.rollback()
        print(f"IMPORT FAILED: Transaction rolled back. Error: {str(e)}")
        return False
    finally:
        session.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import transport data from CSV files.")
    parser.add_argument("--dir", type=str, default="data", help="Directory containing CSV files")
    parser.add_argument("--dry-run", action="store_true", help="Validate only, do not insert to database")
    parser.add_argument("--db", type=str, default=settings.DATABASE_URL, help="Database URL")
    
    args = parser.parse_args()
    
    success = validate_and_import(args.dir, args.db, args.dry_run)
    if not success:
        sys.exit(1)
