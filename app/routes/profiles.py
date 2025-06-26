from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from app.db import supabase

router = APIRouter()

# Request body model for profile creation
class CreateProfileRequest(BaseModel):
    profile_number: int

@router.get("/")
def get_user_profiles(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.replace("Bearer ", "")
    user_data = supabase.auth.get_user(token)

    if user_data.user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = user_data.user.id

    response = supabase.table("profiles").select("*").eq("user_id", user_id).execute()
    return response.data

@router.post("/create")
def create_profile(
    body: CreateProfileRequest,
    authorization: Optional[str] = Header(None)
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.replace("Bearer ", "")
    user_data = supabase.auth.get_user(token)

    if user_data.user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = user_data.user.id
    
    # Check if user exists in custom 'users' table, if not, insert
    existing_user = supabase.table("users").select("*").eq("id", user_id).execute().data
    if not existing_user:
        supabase.table("users").insert({ "id": user_id }).execute()


    # Enforce max 10 profiles
    existing = supabase.table("profiles").select("*").eq("user_id", user_id).execute().data
    if len(existing) >= 10:
        raise HTTPException(status_code=403, detail="Profile limit reached")

    res = supabase.table("profiles").insert({
        "user_id": user_id,
        "profile_number": body.profile_number
    }).execute()

    return res.data
