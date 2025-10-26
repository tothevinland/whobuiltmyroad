"""
Import Indian Roads from OpenStreetMap to WhoBuiltMyRoad Database

This script fetches roads from OpenStreetMap (starting with National Highways)
and adds them to the MongoDB database with OSM data only (no construction info).

Usage:
    python import_indian_roads.py

Requirements:
    - MongoDB running and accessible
    - Internet connection for Overpass API
    - .env file configured with MONGODB_URL and MONGODB_DB_NAME
"""

import asyncio
import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
from typing import List, Dict, Any
import time
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb+srv://unhook:Shekhar9330@unhook.pzgqjlz.mongodb.net/?retryWrites=true&w=majority&appName=Unhook")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "whobuiltmyroad_db")

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# India bounding box (approximate)
INDIA_BBOX = {
    "min_lat": 6.5,    # Southern tip
    "max_lat": 35.5,   # Northern border
    "min_lng": 68.0,   # Western border
    "max_lng": 97.5    # Eastern border
}


class RoadImporter:
    def __init__(self):
        self.client = None
        self.db = None
        self.imported_count = 0
        self.skipped_count = 0
        self.error_count = 0
    
    async def cleanup_database(self):
        """Delete all existing roads from database"""
        print("\n🗑️  CLEANING UP DATABASE")
        print("=" * 60)
        
        count = await self.db.roads.count_documents({})
        if count == 0:
            print("✅ Database is already empty")
            return
        
        print(f"⚠️  Found {count} existing roads in database")
        response = input(f"Delete all {count} roads? (yes/no): ").strip().lower()
        
        if response in ['yes', 'y']:
            result = await self.db.roads.delete_many({})
            print(f"✅ Deleted {result.deleted_count} roads")
        else:
            print("⏭️  Skipped cleanup")
        
    async def connect_db(self):
        """Connect to MongoDB"""
        print(f"🔌 Connecting to MongoDB: {MONGODB_URL}")
        self.client = AsyncIOMotorClient(MONGODB_URL)
        self.db = self.client[MONGODB_DB_NAME]
        print(f"✅ Connected to database: {MONGODB_DB_NAME}")
        
    async def close_db(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            print("🔌 MongoDB connection closed")
    
    async def query_overpass(self, query: str) -> Dict[str, Any]:
        """Query Overpass API"""
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    OVERPASS_URL,
                    data={"data": query},
                    headers={"User-Agent": "WhoBuiltMyRoad-Importer/1.0"}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            print(f"❌ Overpass API error: {e}")
            return {"elements": []}
    
    async def road_exists(self, osm_way_id: str) -> bool:
        """Check if road already exists in database"""
        existing = await self.db.roads.find_one({"osm_way_id": osm_way_id})
        return existing is not None
    
    async def insert_road(self, road_data: Dict[str, Any]) -> bool:
        """Insert road into database"""
        try:
            # Check if already exists
            if await self.road_exists(road_data["osm_way_id"]):
                self.skipped_count += 1
                return False
            
            # Insert into database
            await self.db.roads.insert_one(road_data)
            self.imported_count += 1
            return True
        except Exception as e:
            print(f"❌ Error inserting road {road_data.get('road_name', 'Unknown')}: {e}")
            self.error_count += 1
            return False
    
    def convert_to_road_document(self, osm_element: Dict[str, Any]) -> Dict[str, Any]:
        """Convert OSM element to our road document format"""
        tags = osm_element.get("tags", {})
        
        # Get road name (prefer name, then ref, then alt_name)
        road_name = (
            tags.get("name") or 
            tags.get("ref") or 
            tags.get("alt_name") or 
            f"Unnamed Road (OSM {osm_element['id']})"
        )
        
        # Convert geometry to GeoJSON LineString
        geometry_nodes = osm_element.get("geometry", [])
        if not geometry_nodes:
            return None
        
        coordinates = [
            [node["lon"], node["lat"]]
            for node in geometry_nodes
        ]
        
        geometry = {
            "type": "LineString",
            "coordinates": coordinates
        }
        
        # Calculate center point (approximate - use first point)
        center_lng, center_lat = coordinates[0] if coordinates else [78.9629, 20.5937]
        
        # Get additional info from tags
        highway_type = tags.get("highway", "unknown")
        surface = tags.get("surface", "Unknown")
        lanes = tags.get("lanes", "Unknown")
        
        # Create road document
        # Using placeholder values for construction data since we don't have it yet
        road_doc = {
            "road_name": road_name,
            "location": {
                "type": "Point",
                "coordinates": [center_lng, center_lat]
            },
            # Placeholder values - admin should update these
            "contractor": "To be updated",
            "approved_by": "To be updated",
            "total_cost": "To be updated",
            "promised_completion_date": "To be updated",
            "actual_completion_date": "To be updated",
            "maintenance_firm": "To be updated",
            "status": f"Type: {highway_type}",
            "images": [],
            "added_by_user": "WhoBuiltMyRoad",
            "approved": True,  # Auto-approved
            "extra_fields": {
                "highway_type": highway_type,
                "surface": surface,
                "lanes": lanes,
                "imported_from": "OpenStreetMap",
                "import_date": datetime.now(timezone.utc).isoformat()
            },
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            # OSM data
            "osm_way_id": str(osm_element["id"]),
            "geometry": geometry,
            "has_osm_data": True
        }
        
        return road_doc
    
    async def import_national_highways(self):
        """Import all National Highways in India"""
        print("\n🛣️  IMPORTING NATIONAL HIGHWAYS (NH)")
        print("=" * 60)
        
        # Split India into smaller regions to avoid timeout
        # North, South, East, West regions
        regions = [
            {"name": "North India", "min_lat": 23.5, "max_lat": 35.5, "min_lng": 68.0, "max_lng": 82.0},
            {"name": "South India", "min_lat": 6.5, "max_lat": 23.5, "min_lng": 68.0, "max_lng": 82.0},
            {"name": "East India", "min_lat": 6.5, "max_lat": 35.5, "min_lng": 82.0, "max_lng": 97.5},
        ]
        
        all_elements = []
        
        for region in regions:
            print(f"\n📍 Querying {region['name']}...")
            
            query = f"""
            [out:json][timeout:180];
            (
              way["highway"]["ref"~"NH",i]({region['min_lat']},{region['min_lng']},{region['max_lat']},{region['max_lng']});
            );
            out geom;
            """
            
            result = await self.query_overpass(query)
            elements = result.get("elements", [])
            all_elements.extend(elements)
            print(f"✅ Found {len(elements)} segments in {region['name']}")
            
            # Wait between region queries
            await asyncio.sleep(5)
        
        elements = all_elements
        
        print(f"✅ Found {len(elements)} National Highway segments")
        print(f"💾 Importing to database...\n")
        
        for idx, element in enumerate(elements, 1):
            if element.get("type") != "way":
                continue
            
            road_doc = self.convert_to_road_document(element)
            if road_doc:
                success = await self.insert_road(road_doc)
                if success:
                    print(f"  ✅ [{idx}/{len(elements)}] Imported: {road_doc['road_name']}")
                else:
                    print(f"  ⏭️  [{idx}/{len(elements)}] Skipped (already exists): {road_doc['road_name']}")
            
            # Rate limiting - pause every 10 roads
            if idx % 10 == 0:
                await asyncio.sleep(0.5)
        
        print(f"\n✅ National Highways import complete!")
    
    async def import_state_highways(self):
        """Import State Highways in India"""
        print("\n🛣️  IMPORTING STATE HIGHWAYS (SH)")
        print("=" * 60)
        
        # Split into regions to avoid timeout
        regions = [
            {"name": "North India", "min_lat": 23.5, "max_lat": 35.5, "min_lng": 68.0, "max_lng": 82.0},
            {"name": "South India", "min_lat": 6.5, "max_lat": 23.5, "min_lng": 68.0, "max_lng": 82.0},
            {"name": "East India", "min_lat": 6.5, "max_lat": 35.5, "min_lng": 82.0, "max_lng": 97.5},
        ]
        
        all_elements = []
        
        for region in regions:
            print(f"\n📍 Querying {region['name']}...")
            
            query = f"""
            [out:json][timeout:180];
            (
              way["highway"]["ref"~"SH",i]({region['min_lat']},{region['min_lng']},{region['max_lat']},{region['max_lng']});
            );
            out geom;
            """
            
            result = await self.query_overpass(query)
            elements = result.get("elements", [])
            all_elements.extend(elements)
            print(f"✅ Found {len(elements)} segments in {region['name']}")
            
            await asyncio.sleep(5)
        
        elements = all_elements
        
        print(f"✅ Found {len(elements)} State Highway segments")
        print(f"💾 Importing to database...\n")
        
        for idx, element in enumerate(elements, 1):
            if element.get("type") != "way":
                continue
            
            road_doc = self.convert_to_road_document(element)
            if road_doc:
                success = await self.insert_road(road_doc)
                if success:
                    print(f"  ✅ [{idx}/{len(elements)}] Imported: {road_doc['road_name']}")
                else:
                    print(f"  ⏭️  [{idx}/{len(elements)}] Skipped: {road_doc['road_name']}")
            
            if idx % 10 == 0:
                await asyncio.sleep(0.5)
        
        print(f"\n✅ State Highways import complete!")
    
    async def import_major_roads_by_state(self, state_name: str, bbox: Dict[str, float]):
        """Import major roads for a specific state"""
        print(f"\n🛣️  IMPORTING MAJOR ROADS - {state_name}")
        print("=" * 60)
        
        # Query for primary and secondary roads
        query = f"""
        [out:json][timeout:300];
        (
          way["highway"~"^(motorway|trunk|primary|secondary)$"]({bbox['min_lat']},{bbox['min_lng']},{bbox['max_lat']},{bbox['max_lng']});
        );
        out geom;
        """
        
        print(f"📡 Querying Overpass API for {state_name} major roads...")
        
        result = await self.query_overpass(query)
        elements = result.get("elements", [])
        
        print(f"✅ Found {len(elements)} major road segments in {state_name}")
        print(f"💾 Importing to database...\n")
        
        for idx, element in enumerate(elements, 1):
            if element.get("type") != "way":
                continue
            
            road_doc = self.convert_to_road_document(element)
            if road_doc:
                success = await self.insert_road(road_doc)
                if success:
                    print(f"  ✅ [{idx}/{len(elements)}] Imported: {road_doc['road_name']}")
            
            if idx % 10 == 0:
                await asyncio.sleep(0.5)
        
        print(f"\n✅ {state_name} major roads import complete!")
    
    def print_summary(self):
        """Print import summary"""
        print("\n" + "=" * 60)
        print("📊 IMPORT SUMMARY")
        print("=" * 60)
        print(f"✅ Successfully imported: {self.imported_count} roads")
        print(f"⏭️  Skipped (already exist): {self.skipped_count} roads")
        print(f"❌ Errors: {self.error_count} roads")
        print(f"📊 Total processed: {self.imported_count + self.skipped_count + self.error_count}")
        print("=" * 60)
        print("\n💡 Note: All imported roads are AUTO-APPROVED (approved=True)")
        print("   They will appear publicly immediately.")
        print("   Added by: WhoBuiltMyRoad")
        print("\n🎉 Import complete! Check your database.")


async def main():
    """Main import function"""
    print("=" * 60)
    print("🇮🇳 WHOBUILTMYROAD - INDIAN ROADS IMPORTER")
    print("=" * 60)
    print("\nThis will import roads from OpenStreetMap into your database.")
    print("Starting with National Highways, then State Highways.\n")
    
    importer = RoadImporter()
    
    try:
        # Connect to database
        await importer.connect_db()
        
        # Step 0: Cleanup database (optional)
        await importer.cleanup_database()
        
        # Step 1: Import National Highways (NH)
        await importer.import_national_highways()
        
        # Pause between major queries
        print("\n⏸️  Pausing 10 seconds before next query (Overpass API rate limit)...")
        await asyncio.sleep(10)
        
        # Step 2: Import State Highways (SH)
        await importer.import_state_highways()
        
        # Print summary
        importer.print_summary()
        
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
    finally:
        await importer.close_db()
    
    print("\n✅ Done!")


if __name__ == "__main__":
    print("\n⚠️  WARNING: This will query OpenStreetMap's Overpass API")
    print("   This may take 20-40 minutes for all Indian roads.")
    print("   Roads are split into regions to avoid timeouts.")
    print("   All roads will be AUTO-APPROVED and added by 'WhoBuiltMyRoad'.\n")
    
    asyncio.run(main())

