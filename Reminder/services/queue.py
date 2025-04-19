import asyncio
from fastapi import HTTPException
from bson import ObjectId
from loguru import logger

from Reminder.schemas.reminder import ReminderRequest
from Reminder.services.scheduler import generate_dynamic_reminders

# Queue state
response_map = {}
task_queue = asyncio.Queue()

async def process_queue():
    while True:
        req_id, req_data = await task_queue.get()
        user_id = req_data.user_id

        try:
            logger.debug(f"[QUEUE] Processing reminder for user={user_id}")

            if not ObjectId.is_valid(user_id):
                raise ValueError("Invalid user ID format.")

            result = await generate_dynamic_reminders(user_id)
            response_map[req_id].set_result(result)

        except Exception as e:
            logger.exception(f"[QUEUE] Failed to process reminder for user={user_id}")
            response_map[req_id].set_exception(
                HTTPException(status_code=500, detail=str(e))
            )

        finally:
            task_queue.task_done()

async def start_worker():
    logger.info("[QUEUE] Reminder worker started.")
    asyncio.create_task(process_queue())

async def reminder_task(req: ReminderRequest):
    req_id = id(req)
    future = asyncio.get_event_loop().create_future()
    response_map[req_id] = future
    await task_queue.put((req_id, req))
    return await future