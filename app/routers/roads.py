from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Request, Response
from datetime import datetime, timezone
from bson import ObjectId
from typing import Optional
from app.schemas import (
    RoadCreate, RoadUpdate, RoadResponse, RoadList, APIResponse,
    LocationResponse, GeoJSONCollection, GeoJSONFeature,
    FeedbackCreate, FeedbackResponse, FeedbackList
)
from app.auth import get_current_user, get_current_user_optional
from app.database import get_database
from app.config import settings
from app.utils.storage import r2_storage
from app.utils.datetime_helper import format_datetime_response
from app.utils.rate_limit import (
    limiter,
    RATE_LIMIT_ROAD_CREATE,
    RATE_LIMIT_ROAD_UPDATE,
    RATE_LIMIT_IMAGE_UPLOAD,
    RATE_LIMIT_FEEDBACK_CREATE,
    RATE_LIMIT_READ
)

router = APIRouter(prefix="/roads", tags=["roads"])


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


@router.get("", response_model=APIResponse)
@limiter.limit(RATE_LIMIT_READ)
async def get_roads(
    request: Request,
    response: Response,
    skip: int = 0,
    limit: int = 50
):
    """
    Get all approved roads (public endpoint)
    Rate limit: 500 per hour per IP
    """
    db = get_database()
    
    # Only return approved roads
    cursor = db.roads.find({"approved": True}).sort("created_at", -1).skip(skip).limit(limit)
    roads = await cursor.to_list(length=limit)
    
    total = await db.roads.count_documents({"approved": True})
    
    roads_response = [road_to_response(road) for road in roads]
    
    return APIResponse(
        status="success",
        message="Roads retrieved successfully",
        data={
            "roads": [r.model_dump() for r in roads_response],
            "total": total,
            "skip": skip,
            "limit": limit
        }
    )


@router.get("/map", response_model=APIResponse)
@limiter.limit(RATE_LIMIT_READ)
async def get_roads_geojson(request: Request, response: Response):
    """
    Get all approved roads as GeoJSON for map display
    Rate limit: 500 per hour per IP
    """
    db = get_database()
    
    # Get all approved roads
    cursor = db.roads.find({"approved": True})
    roads = await cursor.to_list(length=None)
    
    features = []
    for road in roads:
        feature = GeoJSONFeature(
            type="Feature",
            geometry={
                "type": "Point",
                "coordinates": road["location"]["coordinates"]  # [lng, lat]
            },
            properties={
                "id": str(road["_id"]),
                "road_name": road["road_name"],
                "contractor": road["contractor"],
                "status": road["status"],
                "total_cost": road["total_cost"]
            }
        )
        features.append(feature)
    
    geojson = GeoJSONCollection(
        type="FeatureCollection",
        features=features
    )
    
    return APIResponse(
        status="success",
        message="GeoJSON retrieved successfully",
        data={"geojson": geojson.model_dump()}
    )


@router.get("/{road_id}", response_model=APIResponse)
@limiter.limit(RATE_LIMIT_READ)
async def get_road_by_id(request: Request, response: Response, road_id: str):
    """
    Get road details by ID (no feedback) - only approved roads
    Rate limit: 500 per hour per IP
    """
    db = get_database()
    
    # Validate ObjectId
    if not ObjectId.is_valid(road_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid road ID"
        )
    
    road = await db.roads.find_one({"_id": ObjectId(road_id), "approved": True})
    if not road:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Road not found"
        )
    
    road_response = road_to_response(road)
    
    return APIResponse(
        status="success",
        message="Road retrieved successfully",
        data={"road": road_response.model_dump()}
    )


@router.get("/{road_id}/feedback", response_model=APIResponse)
@limiter.limit(RATE_LIMIT_READ)
async def get_road_feedback(
    request: Request,
    response: Response,
    road_id: str,
    skip: int = 0,
    limit: int = 50
):
    """
    Get feedback for a specific road (loaded separately)
    Rate limit: 500 per hour per IP
    """
    db = get_database()
    
    # Validate ObjectId
    if not ObjectId.is_valid(road_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid road ID"
        )
    
    # Check if road exists and is approved
    road = await db.roads.find_one({"_id": ObjectId(road_id), "approved": True})
    if not road:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Road not found"
        )
    
    # Get feedback
    cursor = db.feedback.find({"road_id": road_id}).sort("date", -1).skip(skip).limit(limit)
    feedback_list = await cursor.to_list(length=limit)
    
    total = await db.feedback.count_documents({"road_id": road_id})
    
    feedback_response = [
        FeedbackResponse(
            id=str(f["_id"]),
            road_id=f["road_id"],
            user=f["user"],
            comment=f["comment"],
            date=format_datetime_response(f["date"])
        )
        for f in feedback_list
    ]
    
    return APIResponse(
        status="success",
        message="Feedback retrieved successfully",
        data={
            "feedback": [f.model_dump() for f in feedback_response],
            "total": total,
            "skip": skip,
            "limit": limit
        }
    )


@router.post("/{road_id}/feedback", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(RATE_LIMIT_FEEDBACK_CREATE)
async def add_feedback(
    request: Request,
    response: Response,
    road_id: str,
    feedback_data: FeedbackCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Add feedback/comment to a road (requires authentication)
    Rate limit: 30 per hour per IP
    """
    db = get_database()
    
    # Validate ObjectId
    if not ObjectId.is_valid(road_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid road ID"
        )
    
    # Check if road exists and is approved
    road = await db.roads.find_one({"_id": ObjectId(road_id), "approved": True})
    if not road:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Road not found"
        )
    
    # Create feedback
    feedback_dict = {
        "road_id": road_id,
        "user": current_user["username"],
        "comment": feedback_data.comment,
        "date": datetime.now(timezone.utc)
    }
    
    result = await db.feedback.insert_one(feedback_dict)
    
    # Get the created feedback
    created_feedback = await db.feedback.find_one({"_id": result.inserted_id})
    
    feedback_response = FeedbackResponse(
        id=str(created_feedback["_id"]),
        road_id=created_feedback["road_id"],
        user=created_feedback["user"],
        comment=created_feedback["comment"],
        date=format_datetime_response(created_feedback["date"])
    )
    
    return APIResponse(
        status="success",
        message="Feedback added successfully",
        data={"feedback": feedback_response.model_dump()}
    )


@router.post("", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(RATE_LIMIT_ROAD_CREATE)
async def create_road(
    request: Request,
    response: Response,
    road_data: RoadCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Add a new road (pending approval)
    Rate limit: 20 per hour per IP
    """
    db = get_database()
    
    # Create road document
    road_dict = {
        "road_name": road_data.road_name,
        "location": {
            "type": "Point",
            "coordinates": [road_data.location.lng, road_data.location.lat]  # [lng, lat] for GeoJSON
        },
        "contractor": road_data.contractor,
        "approved_by": road_data.approved_by,
        "total_cost": road_data.total_cost,
        "promised_completion_date": road_data.promised_completion_date,
        "actual_completion_date": road_data.actual_completion_date,
        "maintenance_firm": road_data.maintenance_firm,
        "status": road_data.status,
        "images": [],
        "added_by_user": current_user["username"],
        "approved": False,  # Pending approval
        "extra_fields": road_data.extra_fields,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    result = await db.roads.insert_one(road_dict)
    
    return APIResponse(
        status="success",
        message="Road submitted for approval",
        data={
            "road_id": str(result.inserted_id),
            "approved": False
        }
    )


@router.put("/{road_id}", response_model=APIResponse)
@limiter.limit(RATE_LIMIT_ROAD_UPDATE)
async def update_road(
    request: Request,
    response: Response,
    road_id: str,
    road_data: RoadUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    Update a road (creates a pending update, requires approval)
    Rate limit: 30 per hour per IP
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
    
    # Build update dict (only include fields that are provided)
    update_fields = {}
    if road_data.road_name is not None:
        update_fields["road_name"] = road_data.road_name
    if road_data.location is not None:
        update_fields["location"] = {
            "type": "Point",
            "coordinates": [road_data.location.lng, road_data.location.lat]
        }
    if road_data.contractor is not None:
        update_fields["contractor"] = road_data.contractor
    if road_data.approved_by is not None:
        update_fields["approved_by"] = road_data.approved_by
    if road_data.total_cost is not None:
        update_fields["total_cost"] = road_data.total_cost
    if road_data.promised_completion_date is not None:
        update_fields["promised_completion_date"] = road_data.promised_completion_date
    if road_data.actual_completion_date is not None:
        update_fields["actual_completion_date"] = road_data.actual_completion_date
    if road_data.maintenance_firm is not None:
        update_fields["maintenance_firm"] = road_data.maintenance_firm
    if road_data.status is not None:
        update_fields["status"] = road_data.status
    if road_data.extra_fields is not None:
        update_fields["extra_fields"] = road_data.extra_fields
    
    if not update_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    # Mark as pending approval after edit
    update_fields["approved"] = False
    update_fields["updated_at"] = datetime.now(timezone.utc)
    
    # Update road
    await db.roads.update_one(
        {"_id": ObjectId(road_id)},
        {"$set": update_fields}
    )
    
    return APIResponse(
        status="success",
        message="Road update submitted for approval",
        data={
            "road_id": road_id,
            "approved": False
        }
    )


@router.post("/{road_id}/image", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(RATE_LIMIT_IMAGE_UPLOAD)
async def upload_road_image(
    request: Request,
    response: Response,
    road_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Upload an image for a road
    Rate limit: 10 per hour per IP
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
    
    # Validate file type
    if file.content_type not in settings.allowed_image_types_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Only {', '.join(settings.allowed_image_types_list)} are allowed"
        )
    
    # Validate file size
    file_data = await file.read()
    if len(file_data) > settings.max_image_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size too large. Maximum size is {settings.MAX_IMAGE_SIZE_MB}MB"
        )
    
    try:
        # Upload to R2
        image_url = await r2_storage.upload_file(
            file_data=file_data,
            filename=f"road_{road_id}_{file.filename}",
            content_type=file.content_type
        )
        
        # Add image URL to road's images array
        await db.roads.update_one(
            {"_id": ObjectId(road_id)},
            {
                "$push": {"images": image_url},
                "$set": {"updated_at": datetime.now(timezone.utc)}
            }
        )
        
        return APIResponse(
            status="success",
            message="Image uploaded successfully",
            data={"image_url": image_url}
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload image"
        )

