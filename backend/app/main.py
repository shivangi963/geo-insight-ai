from fastapi import FastAPI, HTTPException, status
from typing import List
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from app.agents.local_expert import agent
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))

parent_dir = os.path.dirname(current_dir)

sys.path.insert(0, current_dir)  
sys.path.insert(0, parent_dir)   

print(f"🔧 Current directory: {os.getcwd()}")
print(f"🔧 Script directory: {current_dir}")
print(f"🔧 Parent directory: {parent_dir}")


try:
    # Try relative import first
    from .models import PropertyCreate, PropertyUpdate, PropertyResponse, HealthResponse
    print("✅ Models imported using relative import")
except ImportError as e:
    print(f"⚠️ Relative import failed: {e}")
    try:
        # Try absolute import
        import importlib.util
        
        # Try to find models.py
        models_path = os.path.join(current_dir, "models.py")
        if os.path.exists(models_path):
            spec = importlib.util.spec_from_file_location("models", models_path)
            if spec and spec.loader:
                models_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(models_module)
                PropertyCreate = models_module.PropertyCreate
                PropertyUpdate = models_module.PropertyUpdate
                PropertyResponse = models_module.PropertyResponse
                HealthResponse = models_module.HealthResponse
                print("✅ Models imported using direct file load")
            else:
                raise ImportError("Could not load models.py")
        else:
            print(f"❌ models.py not found at: {models_path}")
            raise ImportError(f"models.py not found")
    except Exception as e2:
        print(f"❌ All import attempts failed: {e2}")
        print("⚠️ Creating inline models as fallback...")
        
        # Create inline models as fallback
        from typing import Optional
        
        class PropertyBase(BaseModel):
            address: str
            city: str
            state: str
            zip_code: str
            price: Optional[float] = None
            bedrooms: Optional[int] = None
            bathrooms: Optional[float] = None
            square_feet: Optional[int] = None
            property_type: Optional[str] = None
            latitude: Optional[float] = None
            longitude: Optional[float] = None

        class PropertyCreate(PropertyBase):
            pass

        class PropertyUpdate(BaseModel):
            address: Optional[str] = None
            city: Optional[str] = None
            state: Optional[str] = None
            zip_code: Optional[str] = None
            price: Optional[float] = None
            bedrooms: Optional[int] = None
            bathrooms: Optional[float] = None
            square_feet: Optional[int] = None
            property_type: Optional[str] = None
            latitude: Optional[float] = None
            longitude: Optional[float] = None

        class PropertyResponse(PropertyBase):
            id: str
            created_at: Optional[str] = None
            updated_at: Optional[str] = None

        class HealthResponse(BaseModel):
            status: str
            timestamp: str
            version: str


try:
    from crud import property_crud
    print("✅ CRUD imported successfully")
except ImportError as e:
    print(f"❌ CRUD import failed: {e}")
    # Create mock CRUD
    print("⚠️ Creating mock CRUD...")
    class MockCRUD:
        def get_all_properties(self, skip=0, limit=100):
            return [
                {
                    "id": "1",
                    "address": "123 Main St",
                    "city": "Test City",
                    "state": "TS",
                    "zip_code": "12345",
                    "price": 500000.0,
                    "bedrooms": 3,
                    "bathrooms": 2.0,
                    "square_feet": 1500,
                    "property_type": "House"
                }
            ]
        def get_property_by_id(self, property_id):
            return self.get_all_properties()[0] if property_id == "1" else None
        def create_property(self, property):
            return {"id": "2", **property.dict()}
        def update_property(self, property_id, property):
            return {"id": property_id, **property.dict()} if property_id == "1" else None
        def delete_property(self, property_id):
            return property_id == "1"
    
    property_crud = MockCRUD()

try:
    from database import Database
    print("✅ Database imported successfully")
except ImportError as e:
    print(f"❌ Database import failed: {e}")
    class Database:
        @staticmethod
        def connect():
            print("📊 Mock database connected")
        @staticmethod
        def close():
            print("📊 Mock database closed")

try:
    from agents.local_expert import agent
    print("✅ Agent imported successfully")
except ImportError:
    print(" Creating placeholder agent...")
    class LocalExpertAgent:
        def process_query(self, query: str):
            return {
                "query": query,
                "answer": f"Phase 3 Demo: I can help analyze '{query}'",
                "success": True
            }
    agent = LocalExpertAgent()



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan"""
    print(" Starting application...")
    try:
        Database.connect()
    except Exception as e:
        print(f"Database connection note: {e}")
    yield
    print(" Shutting down...")
    try:
        Database.close()
    except Exception as e:
        print(f"Database close note: {e}")

app = FastAPI(
    title="GeoInsight AI API",
    description="Backend API for Phase 3 Demo",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        "message": "Welcome to GeoInsight AI API - Phase 3",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "properties": "/api/properties",
            "agent": "POST /api/agent/query"
        }
    }

@app.get("/api/properties", response_model=List[PropertyResponse])
async def get_properties(skip: int = 0, limit: int = 100):
    """Get all properties"""
    properties = property_crud.get_all_properties(skip=skip, limit=limit)
    return properties

@app.get("/api/properties/{property_id}", response_model=PropertyResponse)
async def get_property(property_id: str):
    """Get property by ID"""
    property = property_crud.get_property_by_id(property_id)
    if not property:
        raise HTTPException(status_code=404, detail="Property not found")
    return property

@app.post("/api/properties", response_model=PropertyResponse, status_code=201)
async def create_property(property: PropertyCreate):
    """Create new property"""
    try:
        new_property = property_crud.create_property(property)
        return new_property
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/properties/{property_id}", response_model=PropertyResponse)
async def update_property(property_id: str, property: PropertyUpdate):
    """Update property"""
    updated_property = property_crud.update_property(property_id, property)
    if not updated_property:
        raise HTTPException(status_code=404, detail="Property not found")
    return updated_property

@app.delete("/api/properties/{property_id}")
async def delete_property(property_id: str):
    """Delete property"""
    success = property_crud.delete_property(property_id)
    if not success:
        raise HTTPException(status_code=404, detail="Property not found")
    return {"message": "Property deleted"}

class QueryRequest(BaseModel):
    query: str

@app.post("/api/agent/query")
async def query_agent(request: QueryRequest):
    """Agent query endpoint"""
    try:
        result = agent.process_query(request.query)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)