from app.main import app
for route in app.routes:
    if hasattr(route, "path"):
        print(route.path)
    else:
        print(route)
