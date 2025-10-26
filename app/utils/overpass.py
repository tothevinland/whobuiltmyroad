import httpx
from typing import Dict, Any, List, Optional
from fastapi import HTTPException, status


OVERPASS_URL = "https://overpass-api.de/api/interpreter"


async def query_overpass(query: str, timeout: int = 30) -> Dict[str, Any]:
    """
    Query the Overpass API with the given query string.
    
    Args:
        query: Overpass QL query string
        timeout: Request timeout in seconds
        
    Returns:
        JSON response from Overpass API
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                OVERPASS_URL,
                data={"data": query},
                timeout=timeout,
                headers={"User-Agent": "WhoBuiltMyRoad/1.0"}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Overpass API service temporarily unavailable"
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to connect to Overpass API"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while querying OpenStreetMap data"
        )


async def search_roads_by_name(
    road_name: str,
    lat: float,
    lng: float,
    radius: int = 5000
) -> List[Dict[str, Any]]:
    """
    Search for roads by name within a radius of a location.
    
    Args:
        road_name: Name of the road to search for (case-insensitive)
        lat: Center latitude
        lng: Center longitude
        radius: Search radius in meters (default: 5000)
        
    Returns:
        List of road data with geometry
    """
    # Escape special regex characters in road name, but keep spaces
    escaped_name = road_name.replace('"', '\\"').replace('\\', '\\\\')
    
    # Make the search more flexible by searching for roads that contain the query
    # Use .* before and after to match partial names
    # This will find "NH 44", "National Highway 44", "NH44", etc. when searching for "44"
    flexible_pattern = f".*{escaped_name}.*"
    
    # Overpass QL query - more flexible search
    # Search in name, ref (reference number), and alt_name tags
    query = f"""
    [out:json][timeout:25];
    (
      way["highway"]["name"~"{flexible_pattern}",i](around:{radius},{lat},{lng});
      way["highway"]["ref"~"{flexible_pattern}",i](around:{radius},{lat},{lng});
      way["highway"]["alt_name"~"{flexible_pattern}",i](around:{radius},{lat},{lng});
    );
    out geom;
    """
    
    result = await query_overpass(query)
    
    roads = []
    seen_ids = set()  # Prevent duplicates
    
    for element in result.get("elements", []):
        way_id = str(element["id"])
        
        # Skip if already processed
        if way_id in seen_ids:
            continue
        
        if element.get("type") == "way" and element.get("geometry"):
            seen_ids.add(way_id)
            
            # Convert to GeoJSON LineString
            coordinates = [
                [node["lon"], node["lat"]]
                for node in element.get("geometry", [])
            ]
            
            tags = element.get("tags", {})
            
            # Get best name (prefer name, then ref, then alt_name)
            road_display_name = (
                tags.get("name") or 
                tags.get("ref") or 
                tags.get("alt_name") or 
                "Unnamed Road"
            )
            
            roads.append({
                "osm_way_id": way_id,
                "name": road_display_name,
                "geometry": {
                    "type": "LineString",
                    "coordinates": coordinates
                },
                "tags": tags
            })
    
    return roads


async def get_way_by_id(osm_way_id: str) -> Optional[Dict[str, Any]]:
    """
    Get detailed information about a specific OSM way by its ID.
    
    Args:
        osm_way_id: OpenStreetMap way ID
        
    Returns:
        Way data with geometry, or None if not found
    """
    query = f"""
    [out:json][timeout:25];
    way({osm_way_id});
    out geom;
    """
    
    result = await query_overpass(query)
    
    elements = result.get("elements", [])
    if not elements:
        return None
    
    element = elements[0]
    
    # Convert to GeoJSON LineString
    coordinates = [
        [node["lon"], node["lat"]]
        for node in element.get("geometry", [])
    ]
    
    return {
        "osm_way_id": str(element["id"]),
        "name": element.get("tags", {}).get("name"),
        "geometry": {
            "type": "LineString",
            "coordinates": coordinates
        },
        "tags": element.get("tags", {})
    }


async def get_roads_in_bbox(
    min_lat: float,
    min_lng: float,
    max_lat: float,
    max_lng: float
) -> List[Dict[str, Any]]:
    """
    Get all roads within a bounding box.
    
    Args:
        min_lat: Minimum latitude
        min_lng: Minimum longitude
        max_lat: Maximum latitude
        max_lng: Maximum longitude
        
    Returns:
        List of roads with geometry
    """
    query = f"""
    [out:json][timeout:25];
    (
      way["highway"]({min_lat},{min_lng},{max_lat},{max_lng});
    );
    out geom;
    """
    
    result = await query_overpass(query)
    
    roads = []
    for element in result.get("elements", []):
        if element.get("type") == "way" and element.get("geometry"):
            # Convert to GeoJSON LineString
            coordinates = [
                [node["lon"], node["lat"]]
                for node in element.get("geometry", [])
            ]
            
            roads.append({
                "osm_way_id": str(element["id"]),
                "name": element.get("tags", {}).get("name", "Unnamed Road"),
                "geometry": {
                    "type": "LineString",
                    "coordinates": coordinates
                },
                "tags": element.get("tags", {})
            })
    
    return roads

