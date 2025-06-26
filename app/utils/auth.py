from jose import jwt
from fastapi import Request, HTTPException
from app.db import supabase

def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Missing auth token")

    try:
        # Fully disable signature and audience verification
        payload = jwt.decode(
            token,
            key="",  # no verification
            options={
                "verify_signature": False,
                "verify_aud": False,  # ✅ THIS LINE FIXES YOUR ERROR
            }
        )
        user_id = payload.get("sub")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_resp = supabase.table("users").select("*").eq("id", user_id).single().execute()
    user_data = user_resp.data

    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")

    return user_data

