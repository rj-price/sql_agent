import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.sql_agent import NaturalLanguageToSQL

router = APIRouter()
agent = NaturalLanguageToSQL()


class QuestionRequest(BaseModel):
    question: str


@router.post("/ask")
async def ask_question(request: QuestionRequest):
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, agent.ask_question, request.question)
        return {
            "answer": response.natural_language_answer,
            "sql": response.query_result.sql_query,
            "data": response.query_result.data,
            "columns": response.query_result.column_names,
            "success": response.query_result.success,
            "review": {
                "text": response.review.review_text,
                "corrected_query": response.review.corrected_query,
            } if response.review else None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.get("/schema")
async def get_schema():
    try:
        loop = asyncio.get_event_loop()
        schema = await loop.run_in_executor(None, lambda: agent.schema_info)
        return {"schema": schema}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
