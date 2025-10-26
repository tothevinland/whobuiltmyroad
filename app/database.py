from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

client = None
db = None


async def connect_to_mongo():
    global client, db
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.MONGODB_DB_NAME]
    
    # Create indexes
    await db.users.create_index("username", unique=True)
    await db.roads.create_index([("created_at", -1)])
    await db.roads.create_index([("location", "2dsphere")])  # Geospatial index
    await db.roads.create_index("approved")
    await db.roads.create_index("added_by_user")
    await db.feedback.create_index([("road_id", 1), ("date", -1)])
    await db.feedback.create_index("user")


async def close_mongo_connection():
    global client
    if client:
        client.close()


def get_database():
    return db

