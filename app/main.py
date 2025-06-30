import os
from dotenv import load_dotenv
load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")  # default to 'development'
print(f"[🧪] ENVIRONMENT is: {ENVIRONMENT}")

import multiprocessing
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from app.routes import auth, profiles, products, price_history
from app.routes import ui
from app.scheduler import start as start_scheduler
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")

# Checky change
# 👉 Only apply middleware in production 
if ENVIRONMENT == "production":
    app.add_middleware(HTTPSRedirectMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://panoptes.fly.dev"],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

app.mount("/static", StaticFiles(directory="app/static"), name="static")

# ⬇️ Include all routers
app.include_router(auth.router, prefix="/auth")
app.include_router(profiles.router, prefix="/profiles")
app.include_router(products.router, prefix="/products")
app.include_router(price_history.router, prefix="/history")
app.include_router(ui.router)

@app.on_event("startup")
def startup_event():
    #print("[🛠] FastAPI startup event triggered.")
    #print(f"[🔍] Process name: {multiprocessing.current_process().name}")
    print("[⚠️] Forcing scheduler to start (development override)")
    start_scheduler()

    # ✅ Run a scrape immediately on startup
    from app.scheduler import scrape_all_sites
    scrape_all_sites()

@app.get("/", include_in_schema=False)
def landing_page(request: Request):
    return templates.TemplateResponse("landing.html", {"request": request})

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="Price Monitor API",
        version="1.0.0",
        description="API for tracking product prices and users",
        routes=app.routes,
    )

    # Ensure "components" exists
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}

    # Ensure "securitySchemes" exists under components
    if "securitySchemes" not in openapi_schema["components"]:
        openapi_schema["components"]["securitySchemes"] = {}

    openapi_schema["components"]["securitySchemes"]["bearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT"
    }

    for path in openapi_schema["paths"].values():
        for operation in path.values():
            operation["security"] = [{"bearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

#from app.utils.email import send_alert_email

# @app.get("/test-email")
# def test_email():
    # send_alert_email(
        # to_email="xht@d-blaze.dk",  # 🔁 Replace with your test email
        # product_name="Charizard Ultra Premium Box",
        # product_url="https://www.kelz0r.dk/sample-product",
        # current_price=2739.95
    # )
    # return {"status": "Email sent"}