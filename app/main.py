from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from slowapi.errors import RateLimitExceeded
from app.database import connect_to_mongo, close_mongo_connection
from app.routers import auth, roads, admin, search, osm
from app.config import settings
from app.utils.rate_limit import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_to_mongo()
    
    yield
    
    # Shutdown
    await close_mongo_connection()


app = FastAPI(
    lifespan=lifespan,
    title="WhoBuiltMyRoad API",
    description="Public accountability platform for road infrastructure",
    version="1.0.0"
)

# Add rate limiter state
app.state.limiter = limiter

# Custom rate limit exception handler (minimal info disclosure)
@app.exception_handler(RateLimitExceeded)
async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """
    Custom rate limit handler that doesn't expose sensitive information
    """
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "status": "error",
            "message": "Too many requests. Please try again later.",
            "data": None
        }
    )

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this based on your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Sanitize error messages to avoid exposing sensitive information
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "message": "An unexpected error occurred",
            "data": None
        }
    )


# Include routers
app.include_router(auth.router)
app.include_router(roads.router)
app.include_router(admin.router)
app.include_router(search.router)
app.include_router(osm.router)


@app.get("/")
async def root():
    return {
        "message": "WhoBuiltMyRoad API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "success",
        "message": "API is healthy"
    }

