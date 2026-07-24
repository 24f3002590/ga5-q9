from fastapi import FastAPI
from fastapi.responses import JSONResponse

from schemas import (
    ProposeRequest,
    CommitRequest,
)

app = FastAPI(
    title="Mailroom Agent",
    version="1.0.0",
)


@app.get("/")
async def root():
    return {
        "status": "running",
        "service": "mailroom-agent",
        "version": "1.0.0",
    }


@app.get("/health")
async def health():
    return {
        "status": "ok"
    }


@app.post("/")
async def mailroom(request: ProposeRequest | CommitRequest):
    """
    Single endpoint used by the grader.

    POST /
        operation = propose
        operation = commit
    """

    if request.operation == "propose":
        return JSONResponse(
            {
                "message": "Propose endpoint not implemented yet."
            }
        )

    if request.operation == "commit":
        return JSONResponse(
            {
                "message": "Commit endpoint not implemented yet."
            }
        )

    return JSONResponse(
        status_code=400,
        content={
            "error": "Invalid operation"
        },
    )
