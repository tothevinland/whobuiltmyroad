from fastapi import APIRouter, HTTPException, status, Request, Response
from typing import List
import httpx
from app.schemas import APIResponse, SearchResult
from app.utils.rate_limit import limiter, RATE_LIMIT_READ

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=APIResponse)
@limiter.limit(RATE_LIMIT_READ)
async def search_places(request: Request, response: Response, q: str, limit: int = 5):
    """
    Search for places using OpenStreetMap Nominatim API
    Rate limit: 500 per hour per IP
    """
    if not q or len(q.strip()) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query must be at least 2 characters"
        )
    
    # Limit the number of results
    if limit > 10:
        limit = 10
    
    # Call OpenStreetMap Nominatim API
    nominatim_url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": q,
        "format": "json",
        "limit": limit,
        "addressdetails": 1
    }
    headers = {
        "User-Agent": "WhoBuiltMyRoad/1.0"  # Nominatim requires a User-Agent
    }
    
    try:
        async with httpx.AsyncClient() as client:
            nominatim_response = await client.get(
                nominatim_url,
                params=params,
                headers=headers,
                timeout=10.0
            )
            nominatim_response.raise_for_status()
            results = nominatim_response.json()
        
        # Parse results
        search_results = []
        for result in results:
            search_results.append(SearchResult(
                display_name=result.get("display_name", ""),
                lat=float(result.get("lat", 0)),
                lon=float(result.get("lon", 0)),
                type=result.get("type", ""),
                importance=float(result.get("importance", 0))
            ))
        
        return APIResponse(
            status="success",
            message="Search completed successfully",
            data={"results": [r.model_dump() for r in search_results]}
        )
    
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search service temporarily unavailable"
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search service temporarily unavailable"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during search"
        )

