from fastapi import FastAPI, Request

from app.api.files import router as files_router
from app.schemas.health import HealthResponse
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


app = FastAPI(
    title="Geospatial File Measurement API",
    description="API for processing geographic files and measuring features.",
    version="0.1.0",
)

app.include_router(files_router)


@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check():
    return {
        "status": "ok",
        "message": "Geospatial File Measurement API is running",
    }


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    return JSONResponse(
        status_code=422,
        content={
            "detail": (
                "Request validation failed. "
                "Check required fields and data types."
            )
        },
    )
