from fastapi import FastAPI, HTTPException
import uvicorn
from fastapi.staticfiles import StaticFiles # Import StaticFiles
import os # Import os
from backend.models import ChatRequest, ChatResponse, ExplainSqlRequest, ExplainSqlResponse # Import new models
from backend.services.llm_service import generate_sql_from_query, generate_explanation, explain_sql_query
from backend.services.bigquery_service import execute_query
from backend.services.chart_service import generate_chart_html
from backend.services.vector_store_service import initialize_schema_vector_db # Import for startup
import logging

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    logger.info("Application startup: Initializing schema vector database...")
    initialize_schema_vector_db() # Initialize vector DB
    logger.info("Schema vector database initialization attempt complete.")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mount static directory
# The 'static' directory should be at 'ai_chatbot_project/backend/static'
# __file__ is 'ai_chatbot_project/backend/main.py'
# So, current_dir is 'ai_chatbot_project/backend'
current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(current_dir, "static")

# Ensure the static directory exists
if not os.path.exists(static_dir):
    try:
        os.makedirs(static_dir)
        logger.info(f"Successfully created static directory at: {static_dir}")
    except OSError as e:
        logger.error(f"Failed to create static directory at {static_dir}: {e}", exc_info=True)
        # Handle error appropriately if static dir is critical for app startup

app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.post("/api/chat", response_model=ChatResponse)
async def chat(chat_request: ChatRequest):
    logger.info(f"Received chat request: {chat_request.query}")
    
    organization_id = "test_org_123" 
    
    sql_query = generate_sql_from_query(
        user_query=chat_request.query,
        organization_id=organization_id
    )
    
    final_explanation = "Could not process the request." # Default explanation
    data = None
    chart_url = None

    if not sql_query:
        logger.error("LLM failed to generate SQL query.")
        final_explanation = "Sorry, I couldn't generate a SQL query for your request. Please try rephrasing."
    else:
        logger.info(f"Generated SQL query: {sql_query}")
        data, bq_error = execute_query(sql_query=sql_query, organization_id=organization_id)

        if bq_error:
            logger.error(f"BigQuery execution error: {bq_error}")
            # The explanation from generate_explanation will handle the bq_error context.
            # We pass None for data to ensure it mentions no data was retrieved.
            data = None # Explicitly set data to None on BQ error
            # Attempt to generate explanation even if BQ fails, to explain the situation
            llm_explanation = generate_explanation(
                user_query=chat_request.query,
                sql_query=sql_query,
                results=None # Pass None as data due to BQ error
            )
            if llm_explanation:
                final_explanation = f"BigQuery Error: {bq_error}. \nLLM Explanation: {llm_explanation}"
            else:
                final_explanation = f"BigQuery Error: {bq_error}. Additionally, the explanation generation failed."

        else: # No BigQuery error
            if data:
                logger.info(f"Data retrieved from BigQuery. Attempting to generate chart for query: {chat_request.query}")
                chart_url = generate_chart_html(data=data, query=chat_request.query)
                if chart_url:
                    logger.info(f"Chart generated successfully: {chart_url}")
            # Generate explanation regardless of chart generation success
            llm_explanation = generate_explanation(
                user_query=chat_request.query,
                sql_query=sql_query,
                results=data
            )
            if llm_explanation:
                final_explanation = llm_explanation
            else:
                final_explanation = "Query executed and data retrieved, but explanation generation failed."
                if not data:
                     final_explanation = "Query executed successfully, but no data was returned, and explanation generation failed."


    return ChatResponse(
        sql_query=sql_query, # can be None if SQL generation failed
        data=data,
        explanation=final_explanation,
        chart_url=chart_url
    )

@app.post("/api/explain-sql", response_model=ExplainSqlResponse)
async def handle_explain_sql(request: ExplainSqlRequest):
    logger.info(f"Received request to explain SQL query: {request.sql_query}")
    
    explanation = explain_sql_query(sql_query=request.sql_query) # explain_sql_query is synchronous
    
    if explanation and not explanation.startswith("Error:"):
        logger.info("Successfully generated SQL explanation.")
        return ExplainSqlResponse(explanation=explanation)
    else:
        logger.error(f"Failed to generate SQL explanation. Reason: {explanation}")
        error_message = explanation if explanation else "Failed to explain SQL query due to an unknown error."
        # If the explanation function itself returns an error message, use it.
        # Otherwise, provide a generic one.
        if explanation and explanation.startswith("Error:"):
             # Pass the specific error from the service if available
            return ExplainSqlResponse(error=explanation)
        return ExplainSqlResponse(error="Failed to explain SQL query.")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
