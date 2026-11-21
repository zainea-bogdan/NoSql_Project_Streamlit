from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pymongo.errors import OperationFailure, PyMongoError

from backend import db
from backend.routes import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        db.create_indexes()
        print("MongoDB connected, indexes ready")
    except Exception as error:
        print("MongoDB not reachable at startup:", error)
    yield
    if db.client is not None:
        db.client.close()


app = FastAPI(title="Wyscout x MongoDB API", lifespan=lifespan)
app.include_router(api_router)


@app.exception_handler(OperationFailure)
def mongo_rejected(request, error):
    return JSONResponse(status_code=400, content={"detail": f"MongoDB rejected the operation: {error.details or error}"})


@app.exception_handler(PyMongoError)
def mongo_unreachable(request, error):
    return JSONResponse(status_code=503, content={"detail": f"MongoDB not reachable: {str(error)[:300]}"})


@app.get("/health", tags=["health"])
def health():
    return db.health()
