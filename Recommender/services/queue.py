# Filename: services/queue.py

import asyncio
from fastapi import HTTPException
from bson import ObjectId
from datetime import datetime
from loguru import logger

from Recommender.schemas.request import RecommendationRequest
from Recommender.services.recommender import get_recommendation
from Recommender.services.trainer import train_user_model
from Recommender.config.db import users, tasks
from Recommender.utils.hash import compute_task_hash
from Recommender.utils.model_loader import load_model_files

# Shared state
task_queue = asyncio.Queue()
response_map = {}
data_hash_map = {}

async def process_queue():
    while True:
        req_id, req_data = await task_queue.get()
        user_id = req_data.user_id

        try:
            logger.debug(f"[QUEUE] Received recommendation request for user={user_id}")

            if not ObjectId.is_valid(user_id):
                raise ValueError("Invalid user ID format.")

            # Create new user profile if it doesn't exist
            user_obj = await users.find_one({"_id": ObjectId(user_id)})
            if not user_obj:
                logger.info(f"[USER] Creating default profile for user={user_id}")
                await users.insert_one({
                    "_id": ObjectId(user_id),
                    "currentEnergyLevel": 5,
                    "currentMood": "Neutral",
                    "createdAt": datetime.utcnow()
                })

            # Fetch user data
            task_history = await tasks.find({"user": ObjectId(user_id), "completed": True}).to_list(length=1000)
            pending_tasks = await tasks.find({"user": ObjectId(user_id), "completed": False}).to_list(length=1000)

            if not pending_tasks:
                logger.info(f"[QUEUE] No pending tasks for user={user_id}")
                response_map[req_id].set_result({
                    "recommended_task_id": None,
                    "error": "No pending tasks available."
                })
                continue  # No need to call task_done() manually; let finally handle it

            new_hash = compute_task_hash(task_history)

            # Train if missing or stale
            try:
                load_model_files(user_id)
            except Exception:
                logger.warning(f"[MODEL] No model found. Training initial model for user={user_id}")
                train_user_model(user_id, task_history)

            if data_hash_map.get(user_id) != new_hash:
                logger.info(f"[MODEL] Stale model detected. Retraining for user={user_id}")
                train_user_model(user_id, task_history)
                data_hash_map[user_id] = new_hash

            # Score all pending tasks
            best_result = None
            best_score = float("-inf")

            for task in pending_tasks:
                try:
                    result = await get_recommendation(user_id, task)
                    score = result.get("score", -1)
                    if score > best_score:
                        best_score = score
                        best_result = task["_id"]
                except Exception as e:
                    logger.error(f"[RECOMMENDER] Error scoring task {task.get('_id')}: {e}")

            response_map[req_id].set_result({
                "recommended_task_id": str(best_result) if best_result else None,
                "error": None if best_result else "No suitable task recommendation found."
            })

        except ValueError as ve:
            logger.warning(f"[VALIDATION] {ve}")
            response_map[req_id].set_exception(HTTPException(status_code=400, detail=str(ve)))

        except Exception as e:
            logger.exception(f"[RECOMMENDER] Error during recommendation for user={user_id}")
            response_map[req_id].set_result({
                "recommended_task_id": None,
                "error": f"Recommender prediction failed: {str(e)}"
            })

        finally:
            task_queue.task_done()
            logger.debug(f"[QUEUE] Finished processing recommendation for user={user_id}")

async def start_worker():
    logger.info("[QUEUE] Recommender worker initialized.")
    asyncio.create_task(process_queue())

async def recommend(req: RecommendationRequest):
    req_id = id(req)
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    response_map[req_id] = future
    await task_queue.put((req_id, req))
    return await future
