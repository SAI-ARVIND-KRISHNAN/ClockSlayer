import asyncio
from fastapi import HTTPException
from bson import ObjectId
from loguru import logger

from Score.schemas.score import ScoreRequest
from Score.services.predictor import predict_scores
from Score.services.trainer import train_user_model
from Score.config.db import tasks, users
from Score.utils.hashing import compute_task_hash

# Global queues and cache
task_queue = asyncio.Queue()
response_map = {}
data_hash_map = {}

async def process_queue():
    while True:
        req_id, req_data = await task_queue.get()

        # Define early for logging and fallback
        user_id = req_data.user_id
        task_id = req_data.task_id

        try:
            logger.debug(f"[QUEUE] Processing request for user={user_id}, task={task_id}")

            if not ObjectId.is_valid(user_id) or not ObjectId.is_valid(task_id):
                raise ValueError("Invalid user or task ID format.")

            user_obj = await users.find_one({"_id": ObjectId(user_id)})
            if not user_obj:
                raise ValueError("User not found.")

            task_obj = await tasks.find_one({"_id": ObjectId(task_id)})
            if not task_obj:
                raise ValueError("Task not found.")

            if task_obj.get("user") != ObjectId(user_id):
                raise PermissionError("Task not linked to the user.")

            task_history = await tasks.find({"user": ObjectId(user_id), "completed": True}).to_list(length=1000)
            new_hash = compute_task_hash(task_history)

            if data_hash_map.get(user_id) != new_hash:
                logger.info(f"[MODEL] Detected new task history. Retraining model for user {user_id}")
                await train_user_model(user_id, task_history)
                data_hash_map[user_id] = new_hash

            result = await predict_scores(user_id, task_id)
            response_map[req_id].set_result(result)

        except ValueError as ve:
            logger.warning(f"[VALIDATION] {ve}")
            response_map[req_id].set_exception(HTTPException(status_code=400, detail=str(ve)))

        except PermissionError as pe:
            logger.warning(f"[PERMISSION] {pe}")
            response_map[req_id].set_exception(HTTPException(status_code=403, detail=str(pe)))

        except Exception as e:
            logger.exception(f"[PREDICT] Unhandled error while scoring user={user_id}, task={task_id}")
            response_map[req_id].set_result({
                "productivity_score": -1,
                "distraction_score": -1,
                "error": f"Prediction failed: {str(e)}"
            })

        finally:
            logger.debug(f"[QUEUE] Task complete for user={user_id}, task={task_id}")
            task_queue.task_done()


async def start_worker():
    logger.info("[QUEUE] Worker started.")
    asyncio.create_task(process_queue())

async def score_task(req: ScoreRequest):
    req_id = id(req)
    future = asyncio.get_event_loop().create_future()
    response_map[req_id] = future
    await task_queue.put((req_id, req))
    return await future
