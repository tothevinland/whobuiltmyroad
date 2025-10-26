from datetime import datetime
from typing import Optional, List, Dict, Any
import re
from pydantic import BaseModel, Field, field_validator


# Response Models
class DateTimeResponse(BaseModel):
    """Schema for datetime responses with timezone information"""
    iso: str  # ISO 8601 format with timezone
    timestamp: float  # Unix timestamp in seconds
    timezone: str  # UTC offset string


class APIResponse(BaseModel):
    status: str
    message: str
    data: Optional[dict] = None


# User Schemas
class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9_]+$')
    password: str = Field(..., min_length=6)
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        # Only allow letters, numbers, and underscores
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('Username can only contain letters, numbers, and underscores')
        return v


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[str] = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict  # Contains id, username


# Road Schemas
class LocationInput(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class RoadCreate(BaseModel):
    road_name: str = Field(..., min_length=1, max_length=200)
    location: LocationInput
    contractor: str = Field(..., min_length=1, max_length=200)
    approved_by: str = Field(..., min_length=1, max_length=200)
    total_cost: str = Field(..., min_length=1, max_length=100)
    promised_completion_date: str = Field(..., min_length=1, max_length=100)
    actual_completion_date: str = Field(..., min_length=1, max_length=100)
    maintenance_firm: str = Field(..., min_length=1, max_length=200)
    status: str = Field(..., min_length=1, max_length=100)
    extra_fields: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    @field_validator('road_name', 'contractor', 'approved_by', 'maintenance_firm', 'status')
    @classmethod
    def sanitize_text(cls, v):
        if v is None:
            return v
        return re.sub(r'<[^>]*>', '', v).strip()


class RoadUpdate(BaseModel):
    road_name: Optional[str] = Field(None, min_length=1, max_length=200)
    location: Optional[LocationInput] = None
    contractor: Optional[str] = Field(None, min_length=1, max_length=200)
    approved_by: Optional[str] = Field(None, min_length=1, max_length=200)
    total_cost: Optional[str] = Field(None, min_length=1, max_length=100)
    promised_completion_date: Optional[str] = Field(None, min_length=1, max_length=100)
    actual_completion_date: Optional[str] = Field(None, min_length=1, max_length=100)
    maintenance_firm: Optional[str] = Field(None, min_length=1, max_length=200)
    status: Optional[str] = Field(None, min_length=1, max_length=100)
    extra_fields: Optional[Dict[str, Any]] = None
    
    @field_validator('road_name', 'contractor', 'approved_by', 'maintenance_firm', 'status')
    @classmethod
    def sanitize_text(cls, v):
        if v is None:
            return v
        return re.sub(r'<[^>]*>', '', v).strip()


class LocationResponse(BaseModel):
    lat: float
    lng: float


class RoadResponse(BaseModel):
    id: str
    road_name: str
    location: LocationResponse
    contractor: str
    approved_by: str
    total_cost: str
    promised_completion_date: str
    actual_completion_date: str
    maintenance_firm: str
    status: str
    images: List[str] = Field(default_factory=list)
    added_by_user: str
    approved: bool
    extra_fields: Dict[str, Any] = Field(default_factory=dict)
    created_at: DateTimeResponse
    updated_at: DateTimeResponse


class RoadList(BaseModel):
    roads: List[RoadResponse]
    total: int


class GeoJSONFeature(BaseModel):
    type: str = "Feature"
    geometry: Dict[str, Any]
    properties: Dict[str, Any]


class GeoJSONCollection(BaseModel):
    type: str = "FeatureCollection"
    features: List[GeoJSONFeature]


# Feedback Schemas
class FeedbackCreate(BaseModel):
    comment: str = Field(..., min_length=1, max_length=1000)
    
    @field_validator('comment')
    @classmethod
    def sanitize_comment(cls, v):
        if v is None:
            return v
        return re.sub(r'<[^>]*>', '', v).strip()


class FeedbackResponse(BaseModel):
    id: str
    road_id: str
    user: str
    comment: str
    date: DateTimeResponse


class FeedbackList(BaseModel):
    feedback: List[FeedbackResponse]
    total: int


# Search Schemas
class SearchResult(BaseModel):
    display_name: str
    lat: float
    lon: float
    type: str
    importance: float

