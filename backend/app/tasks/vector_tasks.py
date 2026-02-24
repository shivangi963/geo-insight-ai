from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import List

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="batch_embed_properties")
def batch_embed_task(self, property_ids: List[str]) -> dict:
    total = len(property_ids)
    processed = 0
    skipped = 0
    errors = 0

    logger.info("Batch embed started — %d properties", total)

    from app.database import get_sync_database
    from app.supabase_client import vector_db

    db = get_sync_database()

    for idx, prop_id in enumerate(property_ids, start=1):
        try:
            self.update_state(
                state="PROGRESS",
                meta={
                    "progress": int(idx / total * 100),
                    "processed": processed,
                    "current": prop_id,
                },
            )

            from bson import ObjectId
            try:
                doc = db.properties.find_one({"_id": ObjectId(prop_id)})
            except Exception:
                doc = db.properties.find_one({"id": prop_id})

            if not doc:
                logger.warning("Property '%s' not found — skipping", prop_id)
                skipped += 1
                continue

            image_url = doc.get("image_url") or doc.get("image") or ""
            if not image_url:
                logger.warning(
                    "Property '%s' has no image_url — skipping. Add an image_url field to the property document.",
                    prop_id,
                )
                skipped += 1
                continue

            import requests as req
            resp = req.get(image_url, timeout=10)
            resp.raise_for_status()
            raw_bytes = resp.content

            async def _embed():
                from app.supabase_client import get_embedding_service
                svc = await get_embedding_service()
                return await svc.embed_bytes(raw_bytes)

            embedding = asyncio.run(_embed())

            if embedding is None:
                logger.error("Embedding returned None for '%s'", prop_id)
                errors += 1
                continue

            address = (
                doc.get("address")
                or doc.get("locality", "") + ", " + doc.get("city", "")
            ).strip(", ")

            ok = vector_db.upsert_property(
                property_id=str(prop_id),
                address=address,
                embedding=embedding,
                image_url=image_url,
                metadata={
                    "price": doc.get("price"),
                    "bedrooms": doc.get("bedrooms"),
                    "city": doc.get("city"),
                    "locality": doc.get("locality") or doc.get("region", ""),
                },
            )

            if ok:
                processed += 1
            else:
                errors += 1

        except Exception as exc:
            logger.error("Error processing property '%s': %s", prop_id, exc)
            errors += 1
            continue

    result = {
        "task_id": self.request.id,
        "status": "completed",
        "total": total,
        "processed": processed,
        "skipped": skipped,
        "errors": errors,
        "timestamp": datetime.now().isoformat(),
    }

    logger.info("Batch embed finished: %s", result)
    return result