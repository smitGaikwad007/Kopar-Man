from app.main import app
import json

schema = app.openapi()
if "/api/timetable/search" in schema["paths"]:
    print("YES")
else:
    print("NO, paths:")
    for path in schema["paths"].keys():
        print(path)
