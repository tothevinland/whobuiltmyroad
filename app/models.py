from datetime import datetime, timezone
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field, ConfigDict
from pydantic_core import core_schema
from bson import ObjectId


class PyObjectId(str):
    """Custom type for MongoDB ObjectId that works with Pydantic v2"""
    
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler
    ) -> core_schema.CoreSchema:
        return core_schema.union_schema([
            core_schema.is_instance_schema(ObjectId),
            core_schema.chain_schema([
                core_schema.str_schema(),
                core_schema.no_info_plain_validator_function(cls.validate),
            ])
        ],
        serialization=core_schema.plain_serializer_function_ser_schema(
            lambda x: str(x)
        ))
    
    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if isinstance(v, str) and ObjectId.is_valid(v):
            return ObjectId(v)
        raise ValueError("Invalid ObjectId")


class UserInDB(BaseModel):
    """Database model for users - NOT used for API responses"""
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )
    
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    username: str
    hashed_password: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True


class LocationInDB(BaseModel):
    """GeoJSON Point for MongoDB geospatial queries"""
    type: str = "Point"
    coordinates: List[float]  # [longitude, latitude]


class RoadInDB(BaseModel):
    """Database model for roads - NOT used for API responses"""
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )
    
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    road_name: str
    location: LocationInDB  # GeoJSON Point (kept for backward compatibility)
    contractor: str
    approved_by: str
    total_cost: str
    promised_completion_date: str
    actual_completion_date: str
    maintenance_firm: str
    status: str
    images: List[str] = Field(default_factory=list)
    added_by_user: str  # username
    approved: bool = False
    extra_fields: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # OpenStreetMap integration fields
    osm_way_id: Optional[str] = None  # OpenStreetMap way ID
    geometry: Optional[Dict[str, Any]] = None  # GeoJSON LineString from OSM
    has_osm_data: bool = False  # True if linked to OSM


class FeedbackInDB(BaseModel):
    """Database model for feedback - NOT used for API responses"""
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )
    
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    road_id: str
    user: str  # username
    comment: str
    date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

