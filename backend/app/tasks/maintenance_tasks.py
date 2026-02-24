# REPLACE the entire file content with:
from celery import shared_task
from datetime import datetime, timedelta
from typing import Dict
import traceback
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="cleanup_old_tasks")
def cleanup_old_tasks(self) -> Dict:
    try:
        self.update_state(state='PROGRESS', meta={'status': 'Cleaning up old analyses...'})

        from app.database import get_sync_database
        db = get_sync_database()

        cutoff = datetime.now() - timedelta(hours=24)

        result = db.neighborhood_analyses.delete_many({
            "status": {"$in": ["failed", "pending"]},
            "created_at": {"$lt": cutoff}
        })
        nbr_deleted = result.deleted_count

        result = db.satellite_analyses.delete_many({
            "status": {"$in": ["failed", "pending"]},
            "created_at": {"$lt": cutoff}
        })
        sat_deleted = result.deleted_count

        total = nbr_deleted + sat_deleted
        logger.info(f"Cleanup: removed {total} stale records")

        return {
            'task_id': self.request.id,
            'status': 'COMPLETED',
            'tasks_cleaned': total,
            'timestamp': datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        traceback.print_exc()
        return {
            'task_id': self.request.id,
            'status': 'FAILED',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }


@shared_task(bind=True, name="update_analysis_results")
def update_analysis_results(self, analysis_id: str) -> Dict:
    logger.warning(
        "update_analysis_results called for %s — this task is deprecated. "
        "Status updates now happen in-task.", analysis_id
    )
    return {
        'task_id': self.request.id,
        'analysis_id': analysis_id,
        'status': 'COMPLETED',
        'timestamp': datetime.now().isoformat()
    }


@shared_task(bind=True, name="archive_old_results")
def archive_old_results(self, days_old: int = 30) -> Dict:
    try:
        from app.database import get_sync_database
        db = get_sync_database()

        cutoff = datetime.now() - timedelta(days=days_old)

        result = db.neighborhood_analyses.delete_many({
            "status": "completed",
            "completed_at": {"$lt": cutoff}
        })
        archived = result.deleted_count

        logger.info(f"Archived {archived} analyses older than {days_old} days")

        return {
            'task_id': self.request.id,
            'status': 'COMPLETED',
            'archived_count': archived,
            'timestamp': datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Archive failed: {e}")
        traceback.print_exc()
        return {
            'task_id': self.request.id,
            'status': 'FAILED',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }