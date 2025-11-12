from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ...dependencies import get_db, get_current_user_optional
from ....core.firebase import verify_firebase_token, get_or_create_user
from ....models.user import User

router = APIRouter()

class CreateUserRequest(BaseModel):
    full_name: str
    date_of_birth: Optional[str] = None

class TokenVerificationResponse(BaseModel):
    valid: bool
    firebase_uid: str
    email: str
    name: Optional[str] = None

class UserResponse(BaseModel):
    user_id: str
    email: str
    full_name: str
    date_of_birth: Optional[str] = None

@router.post("/verify-token", response_model=TokenVerificationResponse)
async def verify_token(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization.split(" ")[1]
    firebase_data = verify_firebase_token(token)
    if not firebase_data:
        raise HTTPException(status_code=401, detail="Invalid token")

    firebase_uid = firebase_data.get("uid")
    email = firebase_data.get("email")

    if not firebase_uid or not email:
        raise HTTPException(status_code=401, detail="Invalid token data")

    return TokenVerificationResponse(
        valid=True,
        firebase_uid=firebase_uid,
        email=email,
        name=firebase_data.get("name")
    )

@router.post("/create-user", response_model=UserResponse)
async def create_user(
    request: CreateUserRequest,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization.split(" ")[1]
    firebase_data = verify_firebase_token(token)
    if not firebase_data:
        raise HTTPException(status_code=401, detail="Invalid token")

    firebase_uid = firebase_data.get("uid")
    email = firebase_data.get("email")

    if not firebase_uid or not email:
        raise HTTPException(status_code=401, detail="Invalid token data")

    try:
        user = await get_or_create_user(
            db=db,
            firebase_uid=firebase_uid,
            email=email,
            full_name=request.full_name,
            date_of_birth=request.date_of_birth
        )

        return UserResponse(
            user_id=user.user_id,
            email=user.email,
            full_name=user.full_name,
            date_of_birth=str(user.date_of_birth) if user.date_of_birth else None
        )

    except Exception as e:
        # Handle RAG engine registration failures and other errors
        error_message = str(e)
        if "RAG registration failed" in error_message:
            raise HTTPException(
                status_code=503,
                detail=f"User registration failed due to external service error: {error_message}"
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create user: {error_message}"
            )

@router.get("/me", response_model=Optional[UserResponse])
async def get_current_user(
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    if not current_user:
        return None

    return UserResponse(
        user_id=current_user.user_id,
        email=current_user.email,
        full_name=current_user.full_name,
        date_of_birth=str(current_user.date_of_birth) if current_user.date_of_birth else None
    )