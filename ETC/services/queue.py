import asyncio
from fastapi import HTTPException
from bson import ObjectId
from loguru import logger

from ETC.schemas.etc import TaskRequest
from ETC.services.predictor import predict_etc
from ETC.services.trainer import train_user_model
from ETC.config.db import tasks, users
from ETC.utils.hashing import compute_task_hash

task_queue = asyncio.Queue()
response_map = {}
data_hash_map = {}

async def process_queue():
    while True:
        req_id, req_data = await task_queue.get()
        user_id = req_data.user_id

        try:
            logger.debug(f"[QUEUE] Processing ETC request for user={user_id}")

            if not ObjectId.is_valid(user_id):
                raise ValueError("Invalid user ID format")

            user_obj = await users.find_one({"_id": ObjectId(user_id)})
            if not user_obj:
                raise ValueError("User not found")

            # Retrieve task history
            task_history = await tasks.find({"user": ObjectId(user_id), "completed": True}).to_list(length=1000)
            new_hash = compute_task_hash(task_history)

            if data_hash_map.get(user_id) != new_hash:
                logger.info(f"[MODEL] ETC model stale. Retraining for user {user_id}")
                train_user_model(user_id, task_history)
                data_hash_map[user_id] = new_hash

            result = await predict_etc(user_id, req_data)
            response_map[req_id].set_result(result)

        except ValueError as ve:
            logger.warning(f"[VALIDATION] {ve}")
            response_map[req_id].set_exception(HTTPException(status_code=400, detail=str(ve)))

        except Exception as e:
            logger.exception(f"[PREDICT] ETC prediction failed for user={user_id}")
            response_map[req_id].set_result({
                "etc_minutes": -1,
                "formatted_etc": None,
                "error": f"ETC prediction failed: {str(e)}"
            })

        finally:
            task_queue.task_done()
            logger.debug(f"[QUEUE] Finished ETC request for user={user_id}")

async def start_worker():
    logger.info("[QUEUE] ETC worker started.")
    asyncio.create_task(process_queue())

async def score_etc(req: TaskRequest):
    req_id = id(req)
    loop = asyncio.get_event_loop()
    future = loop.create_future()
    response_map[req_id] = future
    await task_queue.put((req_id, req))
    return await future
