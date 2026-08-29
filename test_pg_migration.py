from sqlalchemy import create_engine
import os
os.system("rm -f test_pg.db")
engine = create_engine("sqlite:///test_pg.db")
with engine.connect() as conn:
    pass
