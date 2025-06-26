from fastapi import APIRouter, Request, Form, Depends, Query
from fastapi.responses import RedirectResponse
from fastapi.responses import HTMLResponse
from app.utils.ui_templates import templates
from app.db import supabase
from starlette.status import HTTP_302_FOUND
from typing import Optional
#import urllib.parse
from app.utils.auth import get_current_user
from datetime import datetime, timedelta
import requests
import os



router = APIRouter()

@router.get("/dashboard")
def dashboard(
    request: Request,
    show_archived: bool = False,
    highlight: Optional[int] = None,
    profile_id: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    # Fetch profiles
    profile_resp = supabase.table("profiles").select("*").eq("user_id", current_user["id"]).execute()
    profiles = profile_resp.data or []
    
    # ⛔️ Fallback: no profiles yet
    if not profiles:
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "products": [],
            "profiles": [],
            "selected_profile_id": None,
            "highlight_id": highlight,
            "show_archived": show_archived,
            "no_profiles": True,  # 👈 flag for the template
        })
    
    # Step 2: Profile selection logic
    profile_ids = [p["id"] for p in profiles]
    selected_profile_id = profile_id or profiles[0]["id"]
    if selected_profile_id not in profile_ids:
        selected_profile_id = profiles[0]["id"]
    
    # Fetch products only for selected profile
    query = supabase.table("tracked_products").select("*").eq("profile_id", selected_profile_id)
    if not show_archived:
        query = query.eq("active", True)

    product_resp = query.execute()
    products = product_resp.data or []
    
    print(f"[🔐] User {current_user['email']} sees {len(products)} products")

    # Step 3: Enrich products
    for product in products:
        site_resp = supabase.table("sites").select("name").eq("id", product["site_id"]).execute()
        product["site_name"] = site_resp.data[0]["name"] if site_resp.data else "Unknown"
        product["highlight"] = (highlight == product["id"])

        one_year_ago = (datetime.utcnow() - timedelta(days=365)).isoformat()

        price_resp = supabase.table("price_history") \
            .select("price, checked_at") \
            .eq("product_id", product["id"]) \
            .gte("checked_at", one_year_ago) \
            .order("checked_at", desc=False) \
            .limit(400) \
            .execute()

        if price_resp.data:
            product["latest_price"] = price_resp.data[0]["price"]
            product["last_checked"] = price_resp.data[0]["checked_at"]
            # 🆕 Add for chart
            product["chart_data"] = [
                {"x": row["checked_at"], "y": row["price"]} for row in reversed(price_resp.data)
            ]
            # Calculate trend
            if len(price_resp.data) >= 2:
                latest_price = price_resp.data[-1]["price"]
                oldest_price = price_resp.data[0]["price"]

                # Round to nearest 0.01 to avoid floating point noise
                lp = round(latest_price, 2)
                op = round(oldest_price, 2)

                if lp > op:
                    product["trend"] = "rising"
                elif lp < op:
                    product["trend"] = "falling"
                else:
                    product["trend"] = "stable"
            else:
                product["trend"] = "unknown"
        else:
            product["latest_price"] = "-"
            product["last_checked"] = "-"
            product["chart_data"] = []

        if price_resp.data:
            product["latest_price"] = price_resp.data[0]["price"]
            product["last_checked"] = price_resp.data[0]["checked_at"]
        else:
            product["latest_price"] = "-"
            product["last_checked"] = "-"

        alert_price = product.get("alert_price")
        direction = product.get("alert_direction")
        latest_price = product.get("latest_price")
        if alert_price and latest_price not in ("-", None):
            if direction == "below" and latest_price <= alert_price:
                product["alert_status"] = "✅ Below"
            elif direction == "above" and latest_price >= alert_price:
                product["alert_status"] = "✅ Above"
            else:
                product["alert_status"] = "–"
        else:
            product["alert_status"] = "–"

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "products": products,
        "profiles": profiles,
        "selected_profile_id": selected_profile_id,
        "highlight_id": highlight,
        "show_archived": show_archived,
        "no_profiles": False,
    })


@router.get("/products/add-ui")
def show_add_product_form(request: Request):
    # Fetch available sites and profiles for dropdowns
    sites = supabase.table("sites").select("id, name").execute().data or []
    profiles = supabase.table("profiles").select("id, name").execute().data or []

    return templates.TemplateResponse("add_product.html", {
        "request": request,
        "sites": sites,
        "profiles": profiles
    })

@router.post("/products/add-ui")
async def submit_add_product_form(
    request: Request,
    profile_id: int = Form(...),
    site_id: int = Form(...),
    product_name: str = Form(...),
    product_url: str = Form(...),
    alert_price: float = Form(...),
    alert_direction: str = Form(...),
    auto_alert: str = Form("false"),
):
    auto_alert_bool = auto_alert.lower() in ["true", "on", "1"]

    data = {
        "profile_id": profile_id,
        "site_id": site_id,
        "product_name": product_name.strip(),
        "product_url": product_url.strip(),
        "alert_price": alert_price,
        "alert_direction": alert_direction,
        "auto_alert": auto_alert_bool,
        "active": True,
    }

    try:
        supabase.table("tracked_products").insert(data).execute()
        print(f"[📝] New product added: {product_name}")

        # Get the new product’s ID
        new_id = supabase.table("tracked_products") \
            .select("id") \
            .eq("product_url", product_url) \
            .order("id", desc=True) \
            .limit(1).execute().data[0]["id"]

        return RedirectResponse(url=f"/dashboard?highlight={new_id}", status_code=HTTP_302_FOUND)
    except Exception as e:
        print(f"[❌] Failed to add product: {e}")

 
 
@router.get("/products/{product_id}/edit")
def edit_product_form(request: Request, product_id: int):
    product_resp = supabase.table("tracked_products").select("*").eq("id", product_id).execute()
    if not product_resp.data:
        return templates.TemplateResponse("404.html", {"request": request})

    product = product_resp.data[0]

    # Fetch dropdown data
    sites = supabase.table("sites").select("id, name").execute().data or []
    profiles = supabase.table("profiles").select("id, name").execute().data or []

    return templates.TemplateResponse("edit_product.html", {
        "request": request,
        "product": product,
        "sites": sites,
        "profiles": profiles,
    })

@router.post("/products/{product_id}/edit")
async def update_product(request: Request, product_id: int):
    form = await request.form()

    try:
        update_data = {
            "profile_id": int(form["profile_id"]),
            "site_id": int(form["site_id"]),
            "product_name": form["product_name"].strip(),
            "product_url": form["product_url"].strip(),
            "alert_price": float(form["alert_price"]),
            "alert_direction": form["alert_direction"],
            "auto_alert": form.get("auto_alert", "").lower() in ["true", "on", "1"]
        }

        supabase.table("tracked_products").update(update_data).eq("id", product_id).execute()
        print(f"[✏️] Updated product ID {product_id}: {update_data}")
    except Exception as e:
        print(f"[❌] Failed to update product ID {product_id}: {e}")

    return RedirectResponse(url="/dashboard", status_code=HTTP_302_FOUND)


@router.post("/products/toggle-active/{product_id}")
def toggle_product_active(request: Request, product_id: int):
    try:
        # Get current status
        current = supabase.table("tracked_products").select("active").eq("id", product_id).single().execute()
        if current.data is None:
            raise Exception("Product not found")

        new_status = not current.data["active"]
        supabase.table("tracked_products").update({"active": new_status}).eq("id", product_id).execute()
        print(f"[🔁] Toggled product {product_id} to {'active' if new_status else 'inactive'}")
    except Exception as e:
        print(f"[❌] Failed to toggle product ID {product_id}: {e}")
    return RedirectResponse(url="/dashboard", status_code=HTTP_302_FOUND)

@router.post("/products/delete/{product_id}")
def delete_product(request: Request, product_id: int):
    try:
        supabase.table("tracked_products").delete().eq("id", product_id).execute()
        print(f"[🗑️] Permanently deleted product ID {product_id}")
    except Exception as e:
        print(f"[❌] Failed to permanently delete product ID {product_id}: {e}")
    return RedirectResponse(url="/dashboard", status_code=HTTP_302_FOUND)

@router.post("/create-profile")
async def create_profile(request: Request, user=Depends(get_current_user)):
    form = await request.form()
    profile_name = form.get("profile_name")

    # Fetch current profiles for user
    profiles = supabase.table("profiles").select("id").eq("user_id", user["id"]).execute().data

    if len(profiles) >= 10:
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "page": "dashboard",
            "profile_error": "⚠️ You have reached the profile limit (10)."
        })

    # Insert new profile
    supabase.table("profiles").insert({
        "user_id": user["id"],
        "name": profile_name
    }).execute()

    return RedirectResponse("/dashboard", status_code=HTTP_302_FOUND)



@router.get("/login", response_class=HTMLResponse)
def show_login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
async def login_user(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    payload = {"email": email, "password": password}
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_API_KEY")

    # Authenticate via Supabase Auth API
    res = requests.post(
        f"{supabase_url}/auth/v1/token?grant_type=password",
        headers={"apikey": supabase_key, "Content-Type": "application/json"},
        json=payload
    )

    if res.status_code == 200:
        token = res.json()["access_token"]
        user_info = res.json().get("user", {})
        user_id = user_info.get("id")
        user_email = user_info.get("email")

        # Fallback to fetch user info if not returned
        if not user_id:
            user_resp = requests.get(
                f"{supabase_url}/auth/v1/user",
                headers={"Authorization": f"Bearer {token}"}
            )
            user_info = user_resp.json()
            user_id = user_info.get("id")
            user_email = user_info.get("email")

        # Check if user is already in our `users` table
        existing = supabase.table("users").select("id").eq("id", user_id).execute()
        if not existing.data:
            supabase.table("users").insert({"id": user_id, "email": user_email, "is_admin": False}).execute()

        # Check if they are admin
        user_resp = supabase.table("users").select("is_admin").eq("id", user_id).execute()
        is_admin = user_resp.data[0]["is_admin"] if user_resp.data else False

        # Set session cookie and redirect
        response = RedirectResponse(
            url="/choose-dashboard" if is_admin else "/dashboard",
            status_code=302
        )
        response.set_cookie("access_token", token, httponly=True, max_age=86400)
        return response

    # If login fails
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": "Invalid email or password"
    })
    
@router.get("/choose-dashboard")
def choose_dashboard_get(request: Request):
    return templates.TemplateResponse("choose_dashboard.html", {"request": request})

@router.get("/admin")
def admin_panel(request: Request, current_user: dict = Depends(get_current_user)):
    # print("[🧪] current_user in /admin:", current_user)  # ✅ Add this line

    if not current_user.get("is_admin"):
        print("[⚠️] Not admin! Redirecting.")
        return RedirectResponse(url="/dashboard", status_code=302)

    return templates.TemplateResponse("admin_panel.html", {
        "request": request,
        "user": current_user
    })

@router.get("/admin/products")
def admin_all_products(request: Request, current_user: dict = Depends(get_current_user)):
    if not current_user.get("is_admin"):
        return RedirectResponse(url="/dashboard", status_code=302)

    users = supabase.table("users").select("id, email, is_admin").execute().data or []
    profiles = supabase.table("profiles").select("id, name, user_id").execute().data or []
    products = supabase.table("tracked_products").select("*").execute().data or []
    sites = supabase.table("sites").select("id, name").execute().data or []

    site_map = {s["id"]: s["name"] for s in sites}
    profile_map = {p["id"]: p for p in profiles}
    user_map = {u["id"]: u for u in users}

    for product in products:
        profile = profile_map.get(product["profile_id"], {})
        product["profile_name"] = profile.get("name", "Unknown")
        product["user_id"] = profile.get("user_id")
        product["user_email"] = user_map.get(product["user_id"], {}).get("email", "Unknown")
        product["site_name"] = site_map.get(product["site_id"], "Unknown")

    return templates.TemplateResponse("admin_all_products.html", {
        "request": request,
        "products": products
    })

@router.post("/admin/products/toggle-active/{product_id}")
def admin_toggle_product_active(request: Request, product_id: int, current_user: dict = Depends(get_current_user)):
    try:
        # Get current status
        current = supabase.table("tracked_products").select("active").eq("id", product_id).single().execute()
        if current.data is None:
            raise Exception("Product not found")

        new_status = not current.data["active"]
        supabase.table("tracked_products").update({"active": new_status}).eq("id", product_id).execute()
        print(f"[🔁] Toggled product {product_id} to {'active' if new_status else 'inactive'}")
    except Exception as e:
        print(f"[❌] Failed to toggle product ID {product_id}: {e}")
    
    if current_user.get("is_admin"):
        return RedirectResponse(url="/admin/products", status_code=HTTP_302_FOUND)
    
    return RedirectResponse(url="/dashboard", status_code=HTTP_302_FOUND)

@router.post("/admin/products/delete/{product_id}")
def admin_delete_product(request: Request, product_id: int, current_user: dict = Depends(get_current_user)):
    try:
        supabase.table("tracked_products").delete().eq("id", product_id).execute()
        print(f"[🗑️] Permanently deleted product ID {product_id}")
    except Exception as e:
        print(f"[❌] Failed to permanently delete product ID {product_id}: {e}")
    
    if current_user.get("is_admin"):
        return RedirectResponse(url="/admin/products", status_code=HTTP_302_FOUND)
    
    return RedirectResponse(url="/dashboard", status_code=HTTP_302_FOUND)

@router.get("/admin/users")
def admin_users(request: Request, current_user: dict = Depends(get_current_user)):
    if not current_user.get("is_admin"):
        return RedirectResponse(url="/dashboard", status_code=302)

    users = supabase.table("users").select("id, email, is_admin").execute().data or []
    profiles = supabase.table("profiles").select("id, user_id").execute().data or []
    products = supabase.table("tracked_products").select("profile_id").execute().data or []

    # Count profiles and products per user
    profile_count = {}
    for profile in profiles:
        profile_count[profile["user_id"]] = profile_count.get(profile["user_id"], 0) + 1

    product_count = {}
    profile_to_user = {p["id"]: p["user_id"] for p in profiles}
    for product in products:
        user_id = profile_to_user.get(product["profile_id"])
        if user_id:
            product_count[user_id] = product_count.get(user_id, 0) + 1

    # Annotate users
    for u in users:
        u["profile_count"] = profile_count.get(u["id"], 0)
        u["product_count"] = product_count.get(u["id"], 0)

    return templates.TemplateResponse("admin_users.html", {
        "request": request,
        "users": users
    })

@router.post("/admin/users/toggle-admin/{user_id}")
def toggle_user_admin(user_id: str, current_user: dict = Depends(get_current_user)):
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Not authorized")

    try:
        user_resp = supabase.table("users").select("is_admin").eq("id", user_id).single().execute()
        current_status = user_resp.data["is_admin"]
        supabase.table("users").update({"is_admin": not current_status}).eq("id", user_id).execute()
        print(f"[🔁] Toggled admin for user {user_id}")
    except Exception as e:
        print(f"[❌] Failed to toggle admin: {e}")

    return RedirectResponse(url="/admin/users", status_code=302)

@router.get("/admin/sites")
def admin_sites(request: Request, current_user: dict = Depends(get_current_user)):
    if not current_user.get("is_admin"):
        return RedirectResponse(url="/dashboard", status_code=302)

    sites = supabase.table("sites").select("*").order("id").execute().data or []

    return templates.TemplateResponse("admin_sites.html", {
        "request": request,
        "sites": sites
    })

@router.post("/admin/sites/add")
def admin_add_site(request: Request, name: str = Form(...), current_user: dict = Depends(get_current_user)):
    if not current_user.get("is_admin"):
        return RedirectResponse(url="/dashboard", status_code=302)

    try:
        supabase.table("sites").insert({"name": name.strip()}).execute()
        print(f"[✅] Added new site: {name}")
    except Exception as e:
        print(f"[❌] Failed to add site: {e}")

    return RedirectResponse(url="/admin/sites", status_code=302)


@router.post("/admin/sites/delete/{site_id}")
def admin_delete_site(request: Request, site_id: int, current_user: dict = Depends(get_current_user)):
    if not current_user.get("is_admin"):
        return RedirectResponse(url="/dashboard", status_code=302)

    try:
        supabase.table("sites").delete().eq("id", site_id).execute()
        print(f"[🗑️] Deleted site ID {site_id}")
    except Exception as e:
        print(f"[❌] Failed to delete site: {e}")

    return RedirectResponse(url="/admin/sites", status_code=302)



@router.get("/register")
def show_register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register")
def handle_register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    if len(password) < 6:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Password must be at least 6 characters"
        })

    payload = {
    "email": email,
    "password": password,
    "options": {
        "emailRedirectTo": "http://localhost:8000/post-confirm"
    }
}
    res = requests.post(
        f"{os.getenv('SUPABASE_URL')}/auth/v1/signup",
        headers={
            "apikey": os.getenv("SUPABASE_API_KEY"),
            "Content-Type": "application/json"
        },
        json=payload
    )

    if res.status_code == 200:
        print(f"[✅] New user registered: {email}")
        return RedirectResponse(url="/login", status_code=302)
    else:
        error_message = res.json().get("msg", "Failed to register user.")
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": error_message
        })

@router.get("/post-confirm")
def post_confirm(request: Request):
    return templates.TemplateResponse("post_confirm.html", {"request": request})

@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_form(request: Request):
    return templates.TemplateResponse("forgot_password.html", {
        "request": request,
        "page": "forgot-password"
    })

@router.post("/forgot-password", response_class=HTMLResponse)
async def send_password_reset_email(request: Request):
    form = await request.form()
    email = form.get("email")
    message = None

    try:
        supabase.auth.reset_password_email(
            email,
            options={
                "redirect_to": "http://localhost:8000/reset-password"
            }
        )
        message = "✅ Password reset email sent. Please check your inbox."
    except Exception as e:
        message = f"❌ Error sending reset email: {str(e)}"

    return templates.TemplateResponse("forgot_password.html", {
        "request": request,
        "page": "forgot-password",
        "message": message
    })

@router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request):
    return templates.TemplateResponse("reset_password.html", {
        "request": request,
        "page": "reset-password",
        "supabase_url": os.environ["SUPABASE_URL"],
        "supabase_anon_key": os.environ["SUPABASE_API_KEY"]
    })
    
@router.get("/post-reset", response_class=HTMLResponse)
async def post_reset_notice(request: Request):
    return templates.TemplateResponse("post_reset.html", {"request": request})


# @router.get("/debug-token")
# def debug_token(request: Request):
    # from jose import jwt
    # token = request.cookies.get("access_token")
    # if not token:
        # return {"error": "No access_token in cookies"}

    # try:
        # decoded = jwt.decode(token, key="", options={"verify_signature": False})
        # return {"decoded": decoded}
    # except Exception as e:
        # return {"error": str(e)}
