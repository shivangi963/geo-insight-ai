from celery import shared_task
from typing import Dict
from datetime import datetime
import asyncio


@shared_task(bind=True, name="process_agent_query")
def process_agent_query_task(self, query: str) -> Dict:
    try:
        self.update_state(state='PROGRESS', meta={'status': 'Processing query...'})

        from app.agents.local_expert import agent

        async def _run():
            return await agent.process_query(query)

        response = asyncio.run(_run())

        return {
            'task_id': self.request.id,
            'status': 'SUCCESS',
            'response': response,
            'timestamp': datetime.now().isoformat()
        }

    except Exception as e:
        return {
            'task_id': self.request.id,
            'status': 'FAILED',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }