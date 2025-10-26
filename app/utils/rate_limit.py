from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request


def get_client_ip(request: Request) -> str:
    """
    Get client IP address from request, checking for proxy headers
    """
    # Check for common proxy headers
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, get the first one (client IP)
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fallback to direct connection IP
    return get_remote_address(request)


# Initialize rate limiter
limiter = Limiter(
    key_func=get_client_ip,
    default_limits=["200 per minute"],  # Default limit for all endpoints
    storage_uri="memory://",  # Use in-memory storage
    headers_enabled=False  # Disable headers to not expose rate limit info
)

# Custom rate limit strings for different endpoint types

# VERY STRICT: Account creation (3 per hour per IP)
RATE_LIMIT_REGISTER = "3 per hour"

# STRICT: Login attempts (10 per hour per IP to prevent brute force)
RATE_LIMIT_LOGIN = "10 per hour"

# MODERATE: Road creation (20 per hour per IP to prevent spam)
RATE_LIMIT_ROAD_CREATE = "20 per hour"

# MODERATE: Road updates (30 per hour per IP)
RATE_LIMIT_ROAD_UPDATE = "30 per hour"

# MODERATE: Image upload (10 per hour per IP)
RATE_LIMIT_IMAGE_UPLOAD = "10 per hour"

# MODERATE: Feedback creation (30 per hour per IP)
RATE_LIMIT_FEEDBACK_CREATE = "30 per hour"

# GENEROUS: Read operations (500 per hour per IP)
RATE_LIMIT_READ = "500 per hour"

# MODERATE: Admin operations (50 per hour per IP)
RATE_LIMIT_ADMIN = "50 per hour"

