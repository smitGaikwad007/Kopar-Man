import pytest
import os
import csv
import tempfile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.database import Base
from scripts.import_transport_data import validate_and_import
from app.models.domain import Bus, Route, Schedule, ParcelCapacity

@pytest.fixture
def temp_data_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d

@pytest.fixture
def db_url(temp_data_dir):
    return f"sqlite:///{temp_data_dir}/test.db"

def write_csv(data_dir, filename, headers, rows):
    path = os.path.join(data_dir, filename)
    with open(path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

def setup_valid_dataset(d):
    write_csv(d, 'buses.csv', 
        ['bus_id','bus_number','service_type','operator','status','parcel_enabled','data_source'],
        [['b1','B-1','EXP','MSRTC','ACTIVE','True','DEMO']]
    )
    write_csv(d, 'routes.csv',
        ['route_id','route_name','origin','destination','active','data_source'],
        [['r1','R-1','Kopargaon','Shirdi','True','DEMO']]
    )
    write_csv(d, 'route_stops.csv',
        ['route_id','stop_sequence','stop_name','latitude','longitude','data_source'],
        [['r1','1','Kopargaon','','','DEMO'], ['r1','2','Shirdi','','','DEMO']]
    )
    write_csv(d, 'schedules.csv',
        ['schedule_id','bus_id','route_id','service_date','departure_time','arrival_time','active','data_source'],
        [['s1','b1','r1','2026-09-01','10:00','11:00','True','DEMO']]
    )
    write_csv(d, 'parcel_capacity.csv',
        ['bus_id','schedule_id','route_id','from_stop','to_stop','max_safe_capacity_kg','reserved_capacity_kg','data_source'],
        [['b1','s1','r1','Kopargaon','Shirdi','100.0','0.0','DEMO']]
    )

def test_1_valid_csv_dataset_imports(temp_data_dir, db_url):
    setup_valid_dataset(temp_data_dir)
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    
    assert validate_and_import(temp_data_dir, db_url) == True
    
    Session = sessionmaker(bind=engine)
    db = Session()
    assert db.query(Bus).count() == 1
    assert db.query(Route).count() == 1
    assert db.query(Schedule).count() == 1

def test_2_duplicate_bus_ids(temp_data_dir, db_url):
    setup_valid_dataset(temp_data_dir)
    # Append duplicate bus
    with open(os.path.join(temp_data_dir, 'buses.csv'), 'a') as f:
        f.write("b1,B-DUPE,EXP,MSRTC,ACTIVE,True,DEMO\n")
    assert validate_and_import(temp_data_dir, db_url, dry_run=True) == False

def test_3_unknown_route_in_stops(temp_data_dir, db_url):
    setup_valid_dataset(temp_data_dir)
    with open(os.path.join(temp_data_dir, 'route_stops.csv'), 'a') as f:
        f.write("r99,3,Rahata,,,DEMO\n")
    assert validate_and_import(temp_data_dir, db_url, dry_run=True) == False

def test_4_unknown_bus_in_schedule(temp_data_dir, db_url):
    setup_valid_dataset(temp_data_dir)
    with open(os.path.join(temp_data_dir, 'schedules.csv'), 'a') as f:
        f.write("s2,b99,r1,2026-09-01,10:00,11:00,True,DEMO\n")
    assert validate_and_import(temp_data_dir, db_url, dry_run=True) == False

def test_5_invalid_stop_ordering(temp_data_dir, db_url):
    setup_valid_dataset(temp_data_dir)
    # The default dataset has Kopargaon=1, Shirdi=2.
    # We will try to add capacity from Shirdi to Kopargaon, which is backwards.
    write_csv(temp_data_dir, 'parcel_capacity.csv',
        ['bus_id','schedule_id','route_id','from_stop','to_stop','max_safe_capacity_kg','reserved_capacity_kg','data_source'],
        [['b1','s1','r1','Shirdi','Kopargaon','100.0','0.0','DEMO']] # Reversed
    )
    assert validate_and_import(temp_data_dir, db_url, dry_run=True) == False


def test_6_capacity_greater_than_max(temp_data_dir, db_url):
    setup_valid_dataset(temp_data_dir)
    write_csv(temp_data_dir, 'parcel_capacity.csv',
        ['bus_id','schedule_id','route_id','from_stop','to_stop','max_safe_capacity_kg','reserved_capacity_kg','data_source'],
        [['b1','s1','r1','Kopargaon','Shirdi','100.0','150.0','DEMO']] # reserved > max
    )
    assert validate_and_import(temp_data_dir, db_url, dry_run=True) == False

def test_7_negative_capacity(temp_data_dir, db_url):
    setup_valid_dataset(temp_data_dir)
    write_csv(temp_data_dir, 'parcel_capacity.csv',
        ['bus_id','schedule_id','route_id','from_stop','to_stop','max_safe_capacity_kg','reserved_capacity_kg','data_source'],
        [['b1','s1','r1','Kopargaon','Shirdi','-100.0','0.0','DEMO']] # Negative
    )
    assert validate_and_import(temp_data_dir, db_url, dry_run=True) == False

def test_8_non_parcel_bus_with_capacity(temp_data_dir, db_url):
    setup_valid_dataset(temp_data_dir)
    write_csv(temp_data_dir, 'buses.csv', 
        ['bus_id','bus_number','service_type','operator','status','parcel_enabled','data_source'],
        [['b1','B-1','EXP','MSRTC','ACTIVE','False','DEMO']] # False
    )
    assert validate_and_import(temp_data_dir, db_url, dry_run=True) == False

def test_9_dry_run_does_not_modify(temp_data_dir, db_url):
    setup_valid_dataset(temp_data_dir)
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    
    assert validate_and_import(temp_data_dir, db_url, dry_run=True) == True
    
    Session = sessionmaker(bind=engine)
    db = Session()
    assert db.query(Bus).count() == 0 # Empty

def test_10_reimport_idempotent(temp_data_dir, db_url):
    setup_valid_dataset(temp_data_dir)
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    
    # First import
    assert validate_and_import(temp_data_dir, db_url) == True
    # Second import
    assert validate_and_import(temp_data_dir, db_url) == True
    
    Session = sessionmaker(bind=engine)
    db = Session()
    # Still 1 record
    assert db.query(Bus).count() == 1
    assert db.query(Route).count() == 1

def test_11_failed_import_rolls_back(temp_data_dir, db_url):
    # This requires forcing a failure during the DB insert phase.
    setup_valid_dataset(temp_data_dir)
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    
    # Intentionally drop a table to cause an exception during insert
    Base.metadata.tables['routes'].drop(engine)
    
    assert validate_and_import(temp_data_dir, db_url) == False
    
    Session = sessionmaker(bind=engine)
    db = Session()
    # Should be rolled back, so buses table is still empty despite bus being inserted before route
    assert db.query(Bus).count() == 0

def test_12_data_source_validation(temp_data_dir, db_url):
    setup_valid_dataset(temp_data_dir)
    write_csv(temp_data_dir, 'buses.csv', 
        ['bus_id','bus_number','service_type','operator','status','parcel_enabled','data_source'],
        [['b1','B-1','EXP','MSRTC','ACTIVE','True','FAKE_SOURCE']] # Invalid
    )
    assert validate_and_import(temp_data_dir, db_url, dry_run=True) == False
