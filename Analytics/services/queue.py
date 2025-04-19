import asyncio
from fastapi import HTTPException
from bson import ObjectId
from loguru import logger

from Analytics.schemas.analytics import AnalyticsRequest
from Analytics.services.analyzer import analyze_user_data

# Queue state
response_map = {}
task_queue = asyncio.Queue()


async def process_queue():
    while True:
        try:
            req_id, req_data = await task_queue.get()
            user_id = getattr(req_data, "user_id", None)

            logger.debug(f"[QUEUE] Processing analytics request for user={user_id}")

            if not user_id or not ObjectId.is_valid(user_id):
                raise HTTPException(status_code=400, detail="Invalid user ID format.")

            result = await analyze_user_data(user_id)
            future = response_map.pop(req_id, None)
            if future:
                future.set_result(result)

        except HTTPException as he:
            logger.warning(f"[QUEUE] HTTP error: {he.detail}")
            future = response_map.pop(req_id, None)
            if future:
                future.set_exception(he)

        except Exception as e:
            logger.exception(f"[QUEUE] Analytics failed: {e}")
            future = response_map.pop(req_id, None)
            if future:
                future.set_exception(HTTPException(status_code=500, detail=str(e)))

        finally:
            task_queue.task_done()


async def start_worker():
    logger.info("[QUEUE] Analytics worker started.")
    asyncio.create_task(process_queue())


async def analyze_task(req: AnalyticsRequest):
    req_id = id(req)
    future = asyncio.get_event_loop().create_future()
    response_map[req_id] = future
    await task_queue.put((req_id, req))
    return await future
