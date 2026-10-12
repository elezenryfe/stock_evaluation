import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()

_job_queues: dict[str, asyncio.Queue] = {}


def get_job_queue(job_id: str) -> asyncio.Queue:
    if job_id not in _job_queues:
        _job_queues[job_id] = asyncio.Queue()
    return _job_queues[job_id]


def push_progress(job_id: str, event_type: str, **kwargs):
    queue = _job_queues.get(job_id)
    if queue is None:
        return
    message = {"type": event_type, **kwargs}
    try:
        queue.put_nowait(message)
    except asyncio.QueueFull:
        pass


def cleanup_job(job_id: str):
    _job_queues.pop(job_id, None)


@router.websocket("/ws/analysis/{job_id}")
async def analysis_progress(websocket: WebSocket, job_id: str):
    await websocket.accept()
    queue = get_job_queue(job_id)

    try:
        while True:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_text(json.dumps(message, default=str))
                if message["type"] in ("complete", "error"):
                    break
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({
                    "type": "timeout",
                    "message": "Analysis timed out waiting for progress",
                }))
                break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"WebSocket error for job {job_id}: {e}")
    finally:
        cleanup_job(job_id)
