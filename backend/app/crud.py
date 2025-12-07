from typing import List, Optional
from bson import ObjectId
from datetime import datetime
from database import Database
from models import PropertyCreate, PropertyUpdate

class PropertyCRUD:
    def __init__(self):
        self.collection = Database.get_collection("properties")

    def create_property(self, property_data: PropertyCreate) -> dict:
        """Create a new property"""
        property_dict = property_data.model_dump()
        property_dict["created_at"] = datetime.utcnow()
        property_dict["updated_at"] = datetime.utcnow()
        
        result = self.collection.insert_one(property_dict)
        created_property = self.collection.find_one({"_id": result.inserted_id})
        created_property["id"] = str(created_property["_id"])
        return created_property

    def get_all_properties(self, skip: int = 0, limit: int = 100) -> List[dict]:
        """Get all properties with pagination"""
        properties = []
        for property in self.collection.find().skip(skip).limit(limit):
            property["id"] = str(property["_id"])
            properties.append(property)
        return properties

    def get_property_by_id(self, property_id: str) -> Optional[dict]:
        """Get property by ID"""
        if not ObjectId.is_valid(property_id):
            return None
            
        property = self.collection.find_one({"_id": ObjectId(property_id)})
        if property:
            property["id"] = str(property["_id"])
        return property

    def update_property(self, property_id: str, property_data: PropertyUpdate) -> Optional[dict]:
        """Update a property"""
        if not ObjectId.is_valid(property_id):
            return None
            
        update_data = {k: v for k, v in property_data.model_dump().items() if v is not None}
        if update_data:
            update_data["updated_at"] = datetime.utcnow()
            self.collection.update_one(
                {"_id": ObjectId(property_id)},
                {"$set": update_data}
            )
        
        updated_property = self.collection.find_one({"_id": ObjectId(property_id)})
        if updated_property:
            updated_property["id"] = str(updated_property["_id"])
        return updated_property

    def delete_property(self, property_id: str) -> bool:
        """Delete a property"""
        if not ObjectId.is_valid(property_id):
            return False
            
        result = self.collection.delete_one({"_id": ObjectId(property_id)})
        return result.deleted_count > 0

# Create CRUD instance
property_crud = PropertyCRUD()