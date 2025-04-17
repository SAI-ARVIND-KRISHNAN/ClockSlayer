from fastapi import FastAPI, HTTPException
from ETC.schemas.etc import TaskRequest
from ETC.services.queue import score_etc, start_worker
from ETC.utils.logger_setup import setup_logger

# Initialize logger first
setup_logger()

app = FastAPI(title="ETC Microservice")

@app.on_event("startup")
async def init_worker():
    await start_worker()

@app.post("/etc", summary="Predict Estimated Time of Completion")
async def predict_etc(req: TaskRequest):
    try:
        return await score_etc(req)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unhandled error: {str(e)}")
