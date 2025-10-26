from fastapi import APIRouter, HTTPException, status, Depends, Request, Response
from datetime import datetime, timezone
from bson import ObjectId
from app.schemas import RoadResponse, APIResponse, LocationResponse
from app.auth import verify_admin_token
from app.database import get_database
from app.utils.datetime_helper import format_datetime_response
from app.utils.rate_limit import limiter, RATE_LIMIT_ADMIN

router = APIRouter(prefix="/admin", tags=["admin"])


def road_to_response(road: dict) -> RoadResponse:
    """Convert database road document to response schema"""
    return RoadResponse(
        id=str(road["_id"]),
        road_name=road["road_name"],
        location=LocationResponse(
            lat=road["location"]["coordinates"][1],
            lng=road["location"]["coordinates"][0]
        ),
        contractor=road["contractor"],
        approved_by=road["approved_by"],
        total_cost=road["total_cost"],
        promised_completion_date=road["promised_completion_date"],
        actual_completion_date=road["actual_completion_date"],
        maintenance_firm=road["maintenance_firm"],
        status=road["status"],
        images=road.get("images", []),
        added_by_user=road["added_by_user"],
        approved=road["approved"],
        extra_fields=road.get("extra_fields", {}),
        created_at=format_datetime_response(road["created_at"]),
        updated_at=format_datetime_response(road["updated_at"])
    )


@router.get("/pending", response_model=APIResponse)
@limiter.limit(RATE_LIMIT_ADMIN)
async def get_pending_roads(
    request: Request,
    response: Response,
    skip: int = 0,
    limit: int = 50,
    admin: dict = Depends(verify_admin_token)
):
    """
    Get all pending roads awaiting approval (admin only - requires API token)
    Rate limit: 50 per hour per IP
    """
    db = get_database()
    
    # Get pending roads
    cursor = db.roads.find({"approved": False}).sort("created_at", -1).skip(skip).limit(limit)
    roads = await cursor.to_list(length=limit)
    
    total = await db.roads.count_documents({"approved": False})
    
    roads_response = [road_to_response(road) for road in roads]
    
    return APIResponse(
        status="success",
        message="Pending roads retrieved successfully",
        data={
            "roads": [r.model_dump() for r in roads_response],
            "total": total,
            "skip": skip,
            "limit": limit
        }
    )


@router.post("/approve/{road_id}", response_model=APIResponse)
@limiter.limit(RATE_LIMIT_ADMIN)
async def approve_road(
    request: Request,
    response: Response,
    road_id: str,
    admin: dict = Depends(verify_admin_token)
):
    """
    Approve a pending road (admin only - requires API token)
    Rate limit: 50 per hour per IP
    """
    db = get_database()
    
    # Validate ObjectId
    if not ObjectId.is_valid(road_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid road ID"
        )
    
    # Check if road exists
    road = await db.roads.find_one({"_id": ObjectId(road_id)})
    if not road:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Road not found"
        )
    
    # Check if already approved
    if road["approved"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Road is already approved"
        )
    
    # Approve road
    await db.roads.update_one(
        {"_id": ObjectId(road_id)},
        {
            "$set": {
                "approved": True,
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    
    # Get updated road
    updated_road = await db.roads.find_one({"_id": ObjectId(road_id)})
    road_response = road_to_response(updated_road)
    
    return APIResponse(
        status="success",
        message="Road approved successfully",
        data={"road": road_response.model_dump()}
    )


@router.delete("/reject/{road_id}", response_model=APIResponse)
@limiter.limit(RATE_LIMIT_ADMIN)
async def reject_road(
    request: Request,
    response: Response,
    road_id: str,
    admin: dict = Depends(verify_admin_token)
):
    """
    Reject and delete a pending road (admin only - requires API token)
    Rate limit: 50 per hour per IP
    """
    db = get_database()
    
    # Validate ObjectId
    if not ObjectId.is_valid(road_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid road ID"
        )
    
    # Check if road exists
    road = await db.roads.find_one({"_id": ObjectId(road_id)})
    if not road:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Road not found"
        )
    
    # Delete associated images from R2 if any
    if road.get("images"):
        from app.utils.storage import r2_storage
        for image_url in road["images"]:
            try:
                await r2_storage.delete_file(image_url)
            except Exception:
                pass  # Continue even if deletion fails
    
    # Delete road
    await db.roads.delete_one({"_id": ObjectId(road_id)})
    
    # Delete associated feedback
    await db.feedback.delete_many({"road_id": road_id})
    
    return APIResponse(
        status="success",
        message="Road rejected and deleted successfully",
        data={"road_id": road_id}
    )

