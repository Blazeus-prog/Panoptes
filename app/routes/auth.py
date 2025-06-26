from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from app.db import supabase

router = APIRouter()

class SignUpModel(BaseModel):
    email: EmailStr
    password: str

class LoginModel(BaseModel):
    email: EmailStr
    password: str

@router.post("/signup")
def signup(data: SignUpModel):
    try:
        res = supabase.auth.sign_up({
            "email": data.email,
            "password": data.password
        })

        if res.user is None:
            raise HTTPException(status_code=400, detail="Signup failed")

        return {"message": "User created. Please check your email to confirm registration."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/login")
def login(data: LoginModel):
    try:
        res = supabase.auth.sign_in_with_password({
            "email": data.email,
            "password": data.password
        })

        # Defensive check: make sure the login was successful
        if not res.session or not res.user:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        return {
            "access_token": res.session.access_token,
            "refresh_token": res.session.refresh_token,
            "user_id": res.user.id,
            "email": res.user.email
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
