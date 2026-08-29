from app.main import app

schema = app.openapi()
for p in schema["paths"].keys():
    print(p)
