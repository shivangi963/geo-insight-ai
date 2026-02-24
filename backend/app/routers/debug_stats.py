
from fastapi import APIRouter, HTTPException
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(tags=["debug-stats"])


@router.get("/api/stats")
async def get_stats():
    try:
        from ..crud import property_crud, get_analysis_count
        from ..database import Database
        
        analysis_count = await get_analysis_count()
        properties = await property_crud.get_all_properties(limit=1000)
        
        total_properties = len(properties)
        
        avg_price = 0
        cities = set()
        if properties:
            prices = [p.get('price', 0) for p in properties if p.get('price')]
            avg_price = sum(prices) / len(prices) if prices else 0
            cities = {p.get('city') for p in properties if p.get('city')}

        uptime = "N/A"
        
        db_connected = await Database.is_connected()
        system_status = "healthy" if db_connected else "degraded"

        return {
            "total_properties": total_properties,
            "total_analyses": analysis_count,
            "unique_cities": len(cities),
            "average_price": round(avg_price, 2),
            "system_status": system_status,
            "uptime": uptime,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to retrieve statistics: {str(e)}"
        )



@router.get("/api/debug/db_info")
async def debug_db_info():
    
    try:
        from ..database import Database
        
        db = await Database.get_database()
        
        server_info = None
        try:
            server_info = await db.client.admin.command('ismaster')
        except Exception:
            try:
                server_info = await db.client.server_info()
            except Exception:
                server_info = {'info': 'unavailable'}

        total = await db.properties.count_documents({})
        sample = []
        cursor = db.properties.find().limit(10)
        async for doc in cursor:
            sample.append({
                'id': str(doc.get('_id')),
                'address': doc.get('address')
            })

        return {
            'server_info': server_info,
            'database': db.name,
            'total_properties': total,
            'sample': sample
        }
    except Exception as e:
        logger.error(f"Debug DB info failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/test/direct-properties")
async def test_direct_properties():

    try:
        from ..crud import property_crud
        from ..database import get_database
    
        db = await get_database()
        count = await db.properties.count_documents({})
        
        properties = await property_crud.get_all_properties(skip=0, limit=10)
        
        return {
            "db_count": count,
            "crud_returned": len(properties),
            "first_property": properties[0] if properties else None,
            "all_properties": properties
        }
    except Exception as e:
        logger.error(f"Test endpoint failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

