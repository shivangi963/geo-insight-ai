import os
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import json

print("✅ crud.py: Modules imported successfully")

class PropertyCRUD:
    """
    Mock CRUD operations for properties
    Uses in-memory data for demo purposes
    """
    
    def __init__(self):
        print("📁 Initializing PropertyCRUD with mock data")
        self.properties = self._load_sample_data()
        self.next_id = len(self.properties) + 1
    
    def _load_sample_data(self) -> List[Dict[str, Any]]:
        """Load sample property data"""
        sample_properties = [
            {
                "id": "1",
                "address": "123 Main St",
                "city": "New York",
                "state": "NY",
                "zip_code": "10001",
                "price": 850000.00,
                "bedrooms": 3,
                "bathrooms": 2.0,
                "square_feet": 1500,
                "property_type": "Apartment",
                "latitude": 40.7489,
                "longitude": -73.9680,
                "created_at": "2024-01-15T10:30:00",
                "updated_at": "2024-01-15T10:30:00"
            },
            {
                "id": "2", 
                "address": "456 Oak Ave",
                "city": "San Francisco",
                "state": "CA",
                "zip_code": "94102",
                "price": 1200000.00,
                "bedrooms": 4,
                "bathrooms": 3.0,
                "square_feet": 2200,
                "property_type": "House",
                "latitude": 37.7749,
                "longitude": -122.4194,
                "created_at": "2024-01-16T14:45:00",
                "updated_at": "2024-01-16T14:45:00"
            },
            {
                "id": "3",
                "address": "789 Pine Rd",
                "city": "Chicago",
                "state": "IL", 
                "zip_code": "60601",
                "price": 550000.00,
                "bedrooms": 2,
                "bathrooms": 1.5,
                "square_feet": 1100,
                "property_type": "Condo",
                "latitude": 41.8781,
                "longitude": -87.6298,
                "created_at": "2024-01-17T09:15:00",
                "updated_at": "2024-01-17T09:15:00"
            },
            {
                "id": "4",
                "address": "101 Maple Ln",
                "city": "Seattle",
                "state": "WA",
                "zip_code": "98101",
                "price": 750000.00,
                "bedrooms": 3,
                "bathrooms": 2.5,
                "square_feet": 1800,
                "property_type": "Townhouse",
                "latitude": 47.6062,
                "longitude": -122.3321,
                "created_at": "2024-01-18T11:20:00",
                "updated_at": "2024-01-18T11:20:00"
            },
            {
                "id": "5",
                "address": "202 Elm St",
                "city": "Austin",
                "state": "TX",
                "zip_code": "73301",
                "price": 650000.00,
                "bedrooms": 3,
                "bathrooms": 2.0,
                "square_feet": 1600,
                "property_type": "House",
                "latitude": 30.2672,
                "longitude": -97.7431,
                "created_at": "2024-01-19T16:30:00",
                "updated_at": "2024-01-19T16:30:00"
            }
        ]
        print(f" Loaded {len(sample_properties)} sample properties")
        return sample_properties
    
    def get_all_properties(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all properties with pagination"""
        print(f"Getting properties (skip={skip}, limit={limit})")
        properties = self.properties[skip:skip + limit]
        print(f" Returning {len(properties)} properties")
        return properties
    
    def get_property_by_id(self, property_id: str) -> Optional[Dict[str, Any]]:
        """Get a property by ID"""
        print(f"🔍 Searching for property ID: {property_id}")
        for prop in self.properties:
            if prop["id"] == property_id:
                print(f"Found property: {prop['address']}")
                return prop
        print(f"Property not found: {property_id}")
        return None
    
    def create_property(self, property_data: BaseModel) -> Dict[str, Any]:
        """Create a new property"""
        print(f"Creating new property: {property_data.address}")
        
        property_dict = property_data.dict()
        property_dict["id"] = str(self.next_id)
        property_dict["created_at"] = "2024-01-20T10:00:00"
        property_dict["updated_at"] = "2024-01-20T10:00:00"
        
        self.properties.append(property_dict)
        self.next_id += 1
        
        print(f"Property created with ID: {property_dict['id']}")
        return property_dict
    
    def update_property(self, property_id: str, property_data: BaseModel) -> Optional[Dict[str, Any]]:
        """Update an existing property"""
        print(f"🔄 Updating property ID: {property_id}")
        
        for i, prop in enumerate(self.properties):
            if prop["id"] == property_id:
                update_data = property_data.dict(exclude_unset=True)
                self.properties[i].update(update_data)
                self.properties[i]["updated_at"] = "2024-01-20T11:00:00"
                
                print(f"Property updated: {self.properties[i]['address']}")
                return self.properties[i]
        
        print(f"Property not found for update: {property_id}")
        return None
    
    def delete_property(self, property_id: str) -> bool:
        """Delete a property"""
        print(f"Deleting property ID: {property_id}")
        
        for i, prop in enumerate(self.properties):
            if prop["id"] == property_id:
                del self.properties[i]
                print(f" Property deleted: {property_id}")
                return True
        
        print(f"Property not found for deletion: {property_id}")
        return False

# Create singleton instance
property_crud = PropertyCRUD()