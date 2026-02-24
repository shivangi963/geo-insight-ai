from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from typing import List, Optional
import logging
import httpx

from ..crud import property_crud
from ..models import PropertyCreate, PropertyUpdate, PropertyResponse
from ..database import Database

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/properties", tags=["properties"])


async def _auto_embed_property(
    property_id: str,
    address: str,
    image_url: str,
    locality: str = "",
    city: str = "",
    price: Optional[float] = None,
    bedrooms: Optional[int] = None,
):
    try:
        from ..supabase_client import vector_db, CLIPEmbeddingService

        if not vector_db.enabled:
            return 

      
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(image_url)
            if resp.status_code != 200:
                logger.warning(f"Image download failed for {property_id}: HTTP {resp.status_code}")
                return
            raw = resp.content

        svc = await CLIPEmbeddingService.get_instance()
        embedding = await svc.embed_bytes(raw)

        if embedding is None:
            logger.warning(f"Embedding returned None for {property_id}")
            return

        ok = vector_db.upsert_property(
            property_id=property_id,
            address=address,
            embedding=embedding,
            image_url=image_url,
            metadata={
                "locality": locality or address.split(",")[0].strip(),
                "city":     city,
                "price":    price,
                "bedrooms": bedrooms,
            },
        )

        if ok:
            logger.info(f"Auto-embedded property {property_id}")
        else:
            logger.warning(f"Supabase upsert failed for {property_id}")

    except Exception as e:
        logger.warning(f"Auto-embed failed for {property_id}: {e}")



@router.get("", response_model=List[PropertyResponse])
async def get_properties(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    city: Optional[str] = None,
):
    
    try:
        logger.info(f"/api/properties called - skip:{skip}, limit:{limit}, city:{city}")

        properties = await property_crud.get_all_properties(skip=skip, limit=limit)
        logger.info(f"   CRUD returned {len(properties)} properties")

        if city:
            properties = [p for p in properties if p.get("city", "").lower() == city.lower()]
            logger.info(f"   After city filter: {len(properties)} properties")

        valid_props = []
        for p in properties:
            try:
                validated = PropertyResponse.model_validate(p)
                valid_props.append(validated)
            except Exception as ve:
                logger.warning(f"Property validation failed (id={p.get('id')}): {ve}")

        logger.info(f"Validation: {len(valid_props)}/{len(properties)} passed")
        return valid_props

    except Exception as e:
        logger.error(f"Failed to get properties: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve properties")


@router.post("", response_model=PropertyResponse, status_code=201)
async def create_property(
    property: PropertyCreate,
    background_tasks: BackgroundTasks,
):
   
    try:
        new_property = await property_crud.create_property(property)

        if property.image_url:
            background_tasks.add_task(
                _auto_embed_property,
                str(new_property.get("id", "")),
                new_property.get("address", ""),
                property.image_url,
              
                locality=new_property.get("locality", ""),
                city=new_property.get("city", ""),
                price=new_property.get("price"),
                bedrooms=new_property.get("bedrooms"),
            )
            logger.info(f"Queued auto-embed for property {new_property.get('id')}")

        logger.info(f"Created property: {new_property.get('id')}")
        return new_property

    except Exception as e:
        logger.error(f"Failed to create property: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{property_id}", response_model=PropertyResponse)
async def get_property(property_id: str):
 
    try:
        prop = await property_crud.get_property_by_id(property_id)
        if not prop:
            raise HTTPException(status_code=404, detail="Property not found")
        return prop
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get property {property_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{property_id}", response_model=PropertyResponse)
async def update_property(property_id: str, property_update: PropertyUpdate):
  
    try:
        updated = await property_crud.update_property(property_id, property_update)
        if not updated:
            raise HTTPException(status_code=404, detail="Property not found")
        return updated
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update property {property_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{property_id}")
async def delete_property(property_id: str):
   
    try:
        deleted = await property_crud.delete_property(property_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Property not found")
        return {"message": "Property deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete property {property_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))