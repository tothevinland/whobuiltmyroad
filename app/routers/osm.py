from fastapi import APIRouter, HTTPException, status, Request, Response, Depends
from typing import List
from app.schemas import APIResponse, OSMRoadSearchResult, OSMWayResponse
from app.database import get_database
from app.utils.overpass import search_roads_by_name, get_way_by_id
from app.utils.rate_limit import limiter, RATE_LIMIT_READ

router = APIRouter(prefix="/osm", tags=["openstreetmap"])


@router.get("/search", response_model=APIResponse)
@limiter.limit(RATE_LIMIT_READ)
async def search_osm_roads(
    request: Request,
    response: Response,
    query: str,
    lat: float,
    lng: float,
    radius: int = 5000
):
    """
    Search for roads in OpenStreetMap by name within a radius.
    
    Args:
        query: Road name to search for (case-insensitive)
        lat: Center latitude
        lng: Center longitude
        radius: Search radius in meters (default: 5000, max: 50000)
    
    Rate limit: 500 per hour per IP
    """
    if not query or len(query.strip()) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query must be at least 2 characters"
        )
    
    # Limit radius to prevent abuse
    if radius > 50000:
        radius = 50000
    
    # Search OSM data
    osm_roads = await search_roads_by_name(query, lat, lng, radius)
    
    # Check which roads have our construction data
    db = get_database()
    results = []
    
    for osm_road in osm_roads:
        # Check if we have data for this OSM way
        our_road = await db.roads.find_one({
            "osm_way_id": osm_road["osm_way_id"],
            "approved": True
        })
        
        results.append(OSMRoadSearchResult(
            osm_way_id=osm_road["osm_way_id"],
            name=osm_road["name"],
            geometry=osm_road["geometry"],
            tags=osm_road.get("tags", {}),
            has_our_data=our_road is not None
        ))
    
    return APIResponse(
        status="success",
        message=f"Found {len(results)} roads in OpenStreetMap",
        data={"results": [r.model_dump() for r in results]}
    )


@router.get("/way/{osm_way_id}", response_model=APIResponse)
@limiter.limit(RATE_LIMIT_READ)
async def get_osm_way(
    request: Request,
    response: Response,
    osm_way_id: str
):
    """
    Get detailed information about a specific OpenStreetMap way.
    
    Args:
        osm_way_id: OpenStreetMap way ID
    
    Rate limit: 500 per hour per IP
    """
    # Fetch from OSM
    way_data = await get_way_by_id(osm_way_id)
    
    if not way_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OpenStreetMap way not found"
        )
    
    way_response = OSMWayResponse(
        osm_way_id=way_data["osm_way_id"],
        name=way_data.get("name"),
        geometry=way_data["geometry"],
        tags=way_data.get("tags", {})
    )
    
    return APIResponse(
        status="success",
        message="OSM way retrieved successfully",
        data={"way": way_response.model_dump()}
    )

