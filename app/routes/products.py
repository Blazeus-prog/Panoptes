from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, HttpUrl
from typing import Optional
from app.db import supabase
from fastapi import Path

router = APIRouter()

# Product creation model
class TrackProductRequest(BaseModel):
    profile_id: int
    site_id: int
    product_name: str
    product_url: HttpUrl
    alert_price: Optional[float] = None
    auto_alert: bool = False

@router.post("/add")
def add_tracked_product(
    body: TrackProductRequest,
    authorization: Optional[str] = Header(None)
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.replace("Bearer ", "")
    user_data = supabase.auth.get_user(token)
    if user_data.user is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Confirm profile belongs to user
    user_id = user_data.user.id
    profile_check = supabase.table("profiles").select("*") \
        .eq("id", body.profile_id).eq("user_id", user_id).execute().data
    if not profile_check:
        raise HTTPException(status_code=403, detail="This profile does not belong to the user.")

    result = supabase.table("tracked_products").insert({
        "profile_id": body.profile_id,
        "site_id": body.site_id,
        "product_name": body.product_name,
        "product_url": str(body.product_url),
        "alert_price": body.alert_price,
        "auto_alert": body.auto_alert,
        "active": True
    }).execute()

    return result.data

@router.get("/profile/{profile_id}")
def get_tracked_products(
    profile_id: int = Path(..., description="ID of the profile to fetch products for"),
    authorization: Optional[str] = Header(None)
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.replace("Bearer ", "")
    user_data = supabase.auth.get_user(token)
    if user_data.user is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = user_data.user.id

    # Validate profile ownership
    profile_check = supabase.table("profiles").select("*") \
        .eq("id", profile_id).eq("user_id", user_id).execute().data
    if not profile_check:
        raise HTTPException(status_code=403, detail="This profile does not belong to the user.")

    products = supabase.table("tracked_products") \
        .select("*").eq("profile_id", profile_id).eq("active", True).execute()

    return products.data

@router.delete("/{product_id}")
def delete_tracked_product(product_id: int, authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.replace("Bearer ", "")
    user_data = supabase.auth.get_user(token)
    if user_data.user is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Optional: check if product belongs to user via profile_id

    result = supabase.table("tracked_products") \
        .update({"active": False}) \
        .eq("id", product_id).execute()

    return {"message": "Product removed from tracking"}
