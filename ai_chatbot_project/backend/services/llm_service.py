import json
import google.generativeai as genai
from langchain.prompts import PromptTemplate
from backend.config import settings
from backend.services.vector_store_service import query_schema # Import for RAG
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# SCHEMA_JSON_STRING is no longer needed here, it's in vector_store_service.py
# and used to populate the vector DB. We'll retrieve parts of it via query_schema.
# Consider moving the canonical SCHEMA_JSON_STRING to a shared config or model file if used elsewhere.
# For now, vector_store_service.py holds its own copy for initialization.

# Updated prompt to use contextual schema parts from vector DB
PROMPT_GUIDELINES = """
You are an AI that generates SQL queries for BigQuery based on user questions.
Your task is to create accurate, safe SQL queries using the provided relevant schema context.
Follow these rules:
1. Generate only SELECT queries.
2. **Crucial:** Always include a condition like "WHERE organization_id = '{organization_id}'" in your SQL queries to filter data for the user's organization. You will be given the organization_id.
3. Use BigQuery-compatible SQL syntax.
4. Return only the SQL query as a raw string, no explanations or additional text like "```sql
...
```".
5. If the question is unclear, generate a query that best matches the intent based on the schema.
6. Ensure proper spacing in aliases (e.g., 'COUNT(*) as count', not 'COUNT(*)as count').
7. Use the fully qualified table name: `visualization-app-404406.mlh_etl_production.mrt_events` if the table name `mrt_events` is mentioned in the context. If other table names appear in the context, use them as appropriate.

Relevant Schema Context from Vector Database:
{contextual_schema_str}

Examples (use these as a style guide, but rely on the provided Relevant Schema Context for actual table/column names):
Question: "How many attendees are doctors in my organization?"
SQL: SELECT COUNT(*) as count FROM `visualization-app-404406.mlh_etl_production.mrt_events` WHERE profession = 'Doctor' AND organization_id = '{organization_id}'

Question: "What is the distribution of attendees by profession for my organization?"
SQL: SELECT profession, COUNT(*) as count FROM `visualization-app-404406.mlh_etl_production.mrt_events` WHERE organization_id = '{organization_id}' GROUP BY profession

User Question: {user_question}
Organization ID: {organization_id}
SQL:
"""

# Generation Config for Gemini
GEMINI_GENERATION_CONFIG = {
    "temperature": 0, # For SQL generation, we want deterministic output
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 2048,
}
GEMINI_EXPLANATION_GENERATION_CONFIG = {
    "temperature": 0.7, # For explanations, a bit more creativity is fine
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 2048,
}
GEMINI_SQL_EXPLANATION_GENERATION_CONFIG = {
    "temperature": 0.3, 
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 2048,
}


def generate_sql_from_query(user_query: str, organization_id: str) -> str | None:
    if not settings.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not found in settings. Cannot generate SQL query.")
        return None
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(model_name='gemini-1.5-pro-latest',
                                      generation_config=GEMINI_GENERATION_CONFIG)

        # Get relevant schema parts from vector store
        logger.info(f"Querying vector store for schema context related to: '{user_query}'")
        relevant_schema_parts = query_schema(user_query=user_query, n_results=7) # Increased n_results
        if not relevant_schema_parts:
            logger.warning("No relevant schema parts found from vector store. SQL generation might be less accurate.")
            contextual_schema_str = "No specific schema context found. Please rely on general knowledge of common table structures if possible."
        else:
            contextual_schema_str = "\n".join(relevant_schema_parts)
        logger.info(f"Contextual schema for prompt:\n{contextual_schema_str}")

        prompt_template = PromptTemplate(
            input_variables=["user_question", "contextual_schema_str", "organization_id"], # Updated input variables
            template=PROMPT_GUIDELINES
        )

        formatted_prompt = prompt_template.format(
            user_question=user_query,
            contextual_schema_str=contextual_schema_str, # Pass the retrieved context
            organization_id=organization_id
        )
        
        logger.info(f"Formatted prompt being sent to Gemini for SQL generation: {formatted_prompt}")
        response = model.generate_content(formatted_prompt)
        
        if response.text:
            sql_query = response.text.strip()
            logger.info(f"Raw Gemini response for SQL query: {sql_query}")

            if sql_query.startswith("```sql"):
                sql_query = sql_query[6:]
            if sql_query.endswith("```"):
                sql_query = sql_query[:-3]
            sql_query = sql_query.strip()

            if sql_query.lower().startswith("select"):
                logger.info(f"Successfully generated SQL query with Gemini: {sql_query}")
                return sql_query
            else:
                logger.warning(f"Gemini response does not appear to be a valid SELECT SQL query: {sql_query}")
                return None
        else:
            logger.error(f"Unexpected Gemini response format (no text) for SQL query: {response.prompt_feedback if response.prompt_feedback else 'No details'}")
            return None

    except Exception as e:
        logger.error(f"Error generating SQL query with Gemini: {e}", exc_info=True)
        return None

EXPLANATION_PROMPT_TEMPLATE = """
User's question: "{user_query}"
SQL query used: "```sql
{sql_query}
```"
Data returned from BigQuery (sample):
{results_sample}

Based on this information, please provide a concise natural language explanation of the data in relation to the user's question.
If no data was returned (indicated by "No data returned." or an empty list in the sample), please state that clearly.
Keep the explanation friendly and easy to understand for a non-technical user.
Avoid simply restating the query or the data verbatim; interpret it.
"""

def generate_explanation(user_query: str, sql_query: str, results: list[dict] | None) -> str | None:
    if not settings.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not found in settings. Cannot generate explanation.")
        return "Error: Gemini API key not configured. Cannot generate explanation."

    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(model_name='gemini-1.5-pro-latest',
                                      generation_config=GEMINI_EXPLANATION_GENERATION_CONFIG)

        results_sample_str: str
        if results:
            sample_to_show = results[:3]
            results_sample_str = json.dumps(sample_to_show, indent=2)
        else:
            results_sample_str = "No data returned."

        prompt_template = PromptTemplate(
            input_variables=["user_query", "sql_query", "results_sample"],
            template=EXPLANATION_PROMPT_TEMPLATE
        )
        formatted_prompt = prompt_template.format(
            user_query=user_query,
            sql_query=sql_query,
            results_sample=results_sample_str
        )
        
        logger.info(f"Formatted explanation prompt being sent to Gemini: {formatted_prompt}")
        response = model.generate_content(formatted_prompt)
        
        if response.text:
            explanation = response.text.strip()
            logger.info(f"Successfully generated explanation with Gemini: {explanation}")
            return explanation
        else:
            logger.error(f"Unexpected Gemini response format (no text) for explanation: {response.prompt_feedback if response.prompt_feedback else 'No details'}")
            return "Error: Could not generate an explanation due to an unexpected response from Gemini."

    except Exception as e:
        logger.error(f"Error generating explanation with Gemini: {e}", exc_info=True)
        return f"Error: An unexpected error occurred while generating the explanation with Gemini: {e}"

SQL_EXPLANATION_PROMPT_TEMPLATE = """
Please explain the following SQL query in detail. Describe its purpose and what each major part of the query does (e.g., SELECT, FROM, WHERE, GROUP BY, JOINs, subqueries).
The explanation should be in natural language and easy for someone with basic SQL knowledge to understand.

SQL Query:
```sql
{sql_query}
```

Explanation:
"""

def explain_sql_query(sql_query: str) -> str | None:
    if not settings.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not found in settings. Cannot explain SQL query.")
        return "Error: Gemini API key not configured. Cannot explain SQL query."

    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(model_name='gemini-1.5-pro-latest',
                                      generation_config=GEMINI_SQL_EXPLANATION_GENERATION_CONFIG)

        prompt_template = PromptTemplate(
            input_variables=["sql_query"],
            template=SQL_EXPLANATION_PROMPT_TEMPLATE
        )
        formatted_prompt = prompt_template.format(sql_query=sql_query)
        
        logger.info(f"Formatted SQL explanation prompt being sent to Gemini: {formatted_prompt}")
        response = model.generate_content(formatted_prompt) 
        
        if response.text: 
            explanation = response.text.strip()
            logger.info(f"Successfully generated SQL explanation with Gemini: {explanation}") 
            return explanation
        else:
            logger.error(f"Unexpected Gemini response format (no text) for SQL explanation: {response.prompt_feedback if response.prompt_feedback else 'No details'}") 
            return "Error: Could not generate an SQL explanation due to an unexpected response from Gemini."

    except Exception as e:
        logger.error(f"Error generating SQL explanation with Gemini: {e}", exc_info=True) 
        return f"Error: An unexpected error occurred while generating the SQL explanation with Gemini: {e}"


if __name__ == '__main__':
    logger.info("Starting LLM service test with Gemini...") 
    if settings.GEMINI_API_KEY: 
        logger.info("GEMINI_API_KEY found. Proceeding with tests.")
        
        sql_test_queries_for_gemini = { 
            "test_org_123": "How many doctors attended events for my organization?",
            "test_org_456": "What is the average event duration for published events in my organization?",
        }
        for org_id, query in sql_test_queries_for_gemini.items(): 
            print(f"\n--- Testing SQL Generation & Data Explanation (Gemini) --- \nQuery='{query}', OrgID='{org_id}'")
            sql = generate_sql_from_query(query, org_id)
            if sql:
                print("Generated SQL (Gemini):\n", sql)
                mock_results = [{"profession": "Doctor", "count": 15}]
                data_explanation = generate_explanation(user_query=query, sql_query=sql, results=mock_results)
                print("Generated Data Explanation (Gemini - with results):\n", data_explanation)
                
                mock_results_none = None
                data_explanation_no_data = generate_explanation(user_query=query, sql_query=sql, results=mock_results_none)
                print("Generated Data Explanation (Gemini - no results):\n", data_explanation_no_data)
            else:
                print("Failed to generate SQL with Gemini.")

        print("\n--- Testing SQL Explanation Function (Gemini) ---") 
        test_sql_to_explain_1 = "SELECT profession, COUNT(DISTINCT attendee_id) AS unique_attendees FROM `visualization-app-404406.mlh_etl_production.mrt_events` WHERE organization_id = 'test_org_123' AND event_status = 'published' GROUP BY profession ORDER BY unique_attendees DESC LIMIT 10;"
        print(f"\nExplaining SQL 1 (Gemini): {test_sql_to_explain_1}") 
        sql_explanation_1 = explain_sql_query(test_sql_to_explain_1)
        print("SQL Explanation 1 (Gemini):\n", sql_explanation_1) 

        test_sql_to_explain_invalid = "SELEC * FRM table" 
        print(f"\nExplaining Invalid SQL (Gemini): {test_sql_to_explain_invalid}") 
        sql_explanation_invalid = explain_sql_query(test_sql_to_explain_invalid)
        print("SQL Explanation (Invalid SQL - Gemini):\n", sql_explanation_invalid) 

    else:
        logger.warning("Skipping tests: GEMINI_API_KEY not configured in .env or backend/.env.") 
        print("Skipping tests: GEMINI_API_KEY not configured. Please set it in .env or backend/.env file.")
# Generation Config for Gemini
# Note: These were defined before, ensuring they are kept.
# GEMINI_GENERATION_CONFIG, GEMINI_EXPLANATION_GENERATION_CONFIG, GEMINI_SQL_EXPLANATION_GENERATION_CONFIG
# ... (rest of the file from the previous correct state)
# ... (rest of the file from the previous correct state)

# The PROMPT_GUIDELINES and generate_sql_from_query function need to be updated.
# Other functions (generate_explanation, explain_sql_query) and the Gemini configs are assumed to be correct from prior steps.
