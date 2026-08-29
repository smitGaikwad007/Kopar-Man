import re
import glob

for filename in ["alembic/versions/2cf9ab210dbd_add_timetable_entries_table.py", "alembic/versions/9c2b1c94862b_add_timetable_departures_table.py"]:
    with open(filename, 'r') as f:
        content = f.read()
    
    # Replace the enum with sa.String() for the migration to avoid Postgres type conflict
    content = re.sub(
        r"sa\.Enum\([^\)]+name='datasource'\)",
        "sa.String()",
        content
    )
    
    with open(filename, 'w') as f:
        f.write(content)
