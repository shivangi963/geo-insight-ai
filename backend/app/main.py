from fastapi import FastAPI, HTTPException, status
from typing import List
from datetime import datetime
from contextlib import asynccontextmanager

from models import PropertyCreate, PropertyUpdate, PropertyResponse, HealthResponse
from crud import property_crud
from database import Database

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - connect to database
    Database.connect()
    yield
    # Shutdown - close database connection
    Database.close()

app = FastAPI(
    title="GeoInsight AI API",
    description="Backend services for GeoInsight AI application",
    version="1.0.0",
    lifespan=lifespan
)

# ✅ EXERCISE 1: Health Check API
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="ok",
        timestamp=datetime.now().isoformat(),
        version="1.0.0"
    )

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to GeoInsight AI API", 
        "docs": "/docs",
        "health": "/health"
    }

# ✅ EXERCISE 2: Real Estate Data API
@app.get("/api/properties", response_model=List[PropertyResponse])
async def get_properties(skip: int = 0, limit: int = 100):
    """Get all properties with pagination"""
    properties = property_crud.get_all_properties(skip=skip, limit=limit)
    return properties

@app.get("/api/properties/{property_id}", response_model=PropertyResponse)
async def get_property(property_id: str):
    """Get a specific property by ID"""
    property = property_crud.get_property_by_id(property_id)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    return property

@app.post("/api/properties", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
async def create_property(property: PropertyCreate):
    """Create a new property"""
    try:
        new_property = property_crud.create_property(property)
        return new_property
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating property: {str(e)}"
        )

@app.put("/api/properties/{property_id}", response_model=PropertyResponse)
async def update_property(property_id: str, property: PropertyUpdate):
    """Update an existing property"""
    updated_property = property_crud.update_property(property_id, property)
    if not updated_property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    return updated_property

@app.delete("/api/properties/{property_id}")
async def delete_property(property_id: str):
    """Delete a property"""
    success = property_crud.delete_property(property_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    return {"message": "Property deleted successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)