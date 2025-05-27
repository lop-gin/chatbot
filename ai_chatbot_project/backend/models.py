from pydantic import BaseModel

class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    sql_query: str | None = None
    explanation: str | None = None
    data: list[dict] | None = None # For table data
    chart_url: str | None = None

class ExplainSqlRequest(BaseModel):
    sql_query: str

class ExplainSqlResponse(BaseModel):
    explanation: str | None = None
    error: str | None = None
