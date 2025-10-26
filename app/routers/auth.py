from fastapi import APIRouter, HTTPException, status, Request, Response
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from app.schemas import UserRegister, UserLogin, APIResponse
from app.auth import get_password_hash, verify_password, create_access_token
from app.database import get_database
from app.config import settings
from app.utils.rate_limit import limiter, RATE_LIMIT_REGISTER, RATE_LIMIT_LOGIN

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(RATE_LIMIT_REGISTER)
async def register_user(request: Request, response: Response, user_data: UserRegister):
    """
    Register a new user - only username and password required
    Rate limit: 3 per hour per IP
    """
    db = get_database()
    
    # Check if username already exists
    existing_username = await db.users.find_one({"username": user_data.username})
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Create user
    user_dict = {
        "username": user_data.username,
        "hashed_password": get_password_hash(user_data.password),
        "is_active": True,
        "created_at": datetime.now(timezone.utc)
    }
    
    result = await db.users.insert_one(user_dict)
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(result.inserted_id)}, expires_delta=access_token_expires
    )
    
    return APIResponse(
        status="success",
        message="User registered successfully",
        data={
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": str(result.inserted_id),
                "username": user_data.username
            }
        }
    )


@router.post("/login", response_model=APIResponse)
@limiter.limit(RATE_LIMIT_LOGIN)
async def login_user(request: Request, response: Response, user_data: UserLogin):
    """
    Login user with username and password
    Rate limit: 10 per hour per IP
    """
    db = get_database()
    
    # Find user by username
    user = await db.users.find_one({"username": user_data.username})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Verify password
    if not verify_password(user_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Check if user is active
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is inactive"
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user["_id"])}, expires_delta=access_token_expires
    )
    
    return APIResponse(
        status="success",
        message="Login successful",
        data={
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": str(user["_id"]),
                "username": user["username"]
            }
        }
    )

