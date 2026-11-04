"""Dashboard statistics.

Counts and averages are computed by MongoDB, so the numbers are exact. (The earlier
version loaded at most 1,000 documents and reported that count as the total.)
"""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException

from ..crud import get_analysis_count
from ..database import Database, get_database

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats")
async def get_stats():
    """Totals shown on the dashboard: properties, analyses, cities, average price."""
    try:
        db = await get_database()
        properties = db["properties"]

        total_properties = await properties.count_documents({})
        cities = await properties.distinct("city")

        average_price = 0.0
        pipeline = [
            {"$match": {"price": {"$gt": 0}}},
            {"$group": {"_id": None, "avg": {"$avg": "$price"}}},
        ]
        async for row in properties.aggregate(pipeline):
            average_price = row.get("avg") or 0.0  # None when no document has a numeric price

        return {
            "total_properties": total_properties,
            "total_analyses": await get_analysis_count(),
            "unique_cities": len([c for c in cities if c]),
            "average_price": round(average_price, 2),
            "system_status": "healthy" if await Database.is_connected() else "degraded",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error("Stats error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")
