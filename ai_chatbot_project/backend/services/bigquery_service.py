from google.cloud import bigquery
from google.cloud.exceptions import GoogleCloudError
from backend.config import settings # Corrected import
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def execute_query(sql_query: str, organization_id: str) -> tuple[list[dict] | None, str | None]:
    """
    Executes a SQL query against BigQuery and returns the results or an error message.

    Args:
        sql_query: The SQL query string.
        organization_id: The organization ID to filter the query by. This is used to replace
                         the '{organization_id}' placeholder in the SQL query.

    Returns:
        A tuple containing a list of dictionaries (query results) and an error message string.
        If successful, error_message is None. If an error occurs, results is None.
    """
    if not settings.BIGQUERY_PROJECT_ID:
        logger.error("BIGQUERY_PROJECT_ID not configured in settings.")
        return None, "Configuration error: BIGQUERY_PROJECT_ID not set. Please check environment variables."

    try:
        # The BigQuery client automatically uses GOOGLE_APPLICATION_CREDENTIALS env var if set.
        client = bigquery.Client(project=settings.BIGQUERY_PROJECT_ID)
        logger.info(f"BigQuery client initialized for project: {settings.BIGQUERY_PROJECT_ID}")
    except Exception as e:
        logger.error(f"Failed to initialize BigQuery client: {e}", exc_info=True)
        return None, f"Failed to initialize BigQuery client: {e}"

    # Parameterize the query by replacing the placeholder
    # IMPORTANT: This is a simple substitution for MVP. For production, use BigQuery client's query parameters.
    if "{organization_id}" not in sql_query:
        logger.warning(
            f"The placeholder '{{organization_id}}' was not found in the SQL query: '{sql_query}'. "
            "The query will be executed as is, but this might lead to unintended data access or errors "
            "if the query was expected to be filtered by organization_id."
        )
        # Depending on policy, you might want to return an error here if the placeholder is mandatory.
        # For this implementation, we'll proceed with the query as-is after logging a warning.
        parameterized_sql_query = sql_query 
    else:
        parameterized_sql_query = sql_query.replace("{organization_id}", organization_id)
    
    logger.info(f"Executing parameterized SQL query for organization '{organization_id}': {parameterized_sql_query}")

    try:
        # No specific QueryJobConfig needed for simple SELECTs without explicit BQ parameters for now.
        query_job = client.query(parameterized_sql_query)
        
        # Wait for the job to complete and fetch results
        results_iterator = query_job.result() # This blocks until the query completes
        
        # Convert rows to a list of dictionaries
        results = [dict(row) for row in results_iterator]
        
        # Limit results to top 10 if not already limited by the query itself.
        # This is a simplistic check. A more robust way would be to parse the SQL for a LIMIT clause
        # or always apply a limit if one isn't present.
        already_limited = "limit" in parameterized_sql_query.lower()
        
        if not already_limited and len(results) > 10:
            logger.info(f"Query did not have an explicit LIMIT clause or returned more than 10 rows. Limiting results to 10 rows from {len(results)}.")
            results = results[:10]
        elif already_limited:
            logger.info(f"Query has an explicit LIMIT clause. Returned {len(results)} rows.")
        else: # Not already limited, but <= 10 results
             logger.info(f"Query did not have an explicit LIMIT clause, returned {len(results)} rows (within 10 row default).")


        logger.info(f"Successfully executed query. Number of rows returned (after potential limit): {len(results)}")
        return results, None

    except GoogleCloudError as e:
        logger.error(f"BigQuery API error during query execution: {e}", exc_info=True)
        # Provide a somewhat more user-friendly error, but include details for debugging
        error_detail = str(e)
        if "Syntax error" in error_detail:
             return None, f"SQL Syntax error in the generated query: {error_detail}"
        return None, f"Error executing BigQuery query: {error_detail}"
    except Exception as e: # Catch any other unexpected errors
        logger.error(f"An unexpected error occurred during BigQuery execution: {e}", exc_info=True)
        return None, f"An unexpected error occurred while processing your request: {e}"

if __name__ == '__main__':
    # This section is for testing and requires:
    # 1. GOOGLE_APPLICATION_CREDENTIALS environment variable set to a valid service account JSON path.
    # 2. BIGQUERY_PROJECT_ID set in your .env file (and loaded by config.py).
    # 3. The service account must have permissions to run queries in the specified project.
    # 4. The table `visualization-app-404406.mlh_etl_production.mrt_events` or similar must exist.
    
    print("Starting BigQuery service test...")
    if not settings.BIGQUERY_PROJECT_ID or not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        print("Skipping test: BIGQUERY_PROJECT_ID not in .env or GOOGLE_APPLICATION_CREDENTIALS env var not set.")
    else:
        print(f"Using Project ID: {settings.BIGQUERY_PROJECT_ID}")
        print(f"Using Credentials Path (from GOOGLE_APPLICATION_CREDENTIALS): {os.getenv('GOOGLE_APPLICATION_CREDENTIALS')}")

        test_org_id = "test_org_123"
        
        # Test 1: Query that should work (assuming table exists)
        # IMPORTANT: Table `visualization-app-404406.mlh_etl_production.mrt_events` is from LLM prompt.
        mock_sql_success = f"SELECT event_title, COUNT(*) as event_count FROM `visualization-app-404406.mlh_etl_production.mrt_events` WHERE organization_id = '{{organization_id}}' GROUP BY event_title LIMIT 3"
        
        print(f"\nTesting successful query for org '{test_org_id}': {mock_sql_success.replace('{organization_id}', test_org_id)}")
        results, error = execute_query(mock_sql_success, test_org_id)
        if error:
            print(f"Error: {error}")
        elif results is not None:
            print("Results:")
            for row in results:
                print(row)
            if not results:
                print("Query executed successfully but returned no results.")
        
        # Test 2: Syntactically incorrect query
        mock_sql_syntax_error = "SELEC * FROM `visualization-app-404406.mlh_etl_production.mrt_events` WHERE organization_id = '{organization_id}'"
        print(f"\nTesting syntax error query for org '{test_org_id}': {mock_sql_syntax_error.replace('{organization_id}', test_org_id)}")
        results_fail, error_fail = execute_query(mock_sql_syntax_error, test_org_id)
        if error_fail:
            print(f"Expected Error: {error_fail}")
        else:
            print("Test failed - expected a syntax error.")

        # Test 3: Query a non-existent table
        mock_sql_not_found = "SELECT * FROM `visualization-app-404406.mlh_etl_production.non_existent_table` WHERE organization_id = '{organization_id}'"
        print(f"\nTesting non-existent table for org '{test_org_id}': {mock_sql_not_found.replace('{organization_id}', test_org_id)}")
        results_nf, error_nf = execute_query(mock_sql_not_found, test_org_id)
        if error_nf:
            print(f"Expected Error (table not found): {error_nf}")
        else:
            print("Test failed - expected table not found error.")

        # Test 4: Query without organization_id placeholder (should log warning & run as is)
        mock_sql_no_placeholder = "SELECT event_title FROM `visualization-app-404406.mlh_etl_production.mrt_events` LIMIT 2"
        print(f"\nTesting query without org_id placeholder: {mock_sql_no_placeholder}")
        results_no_ph, error_no_ph = execute_query(mock_sql_no_placeholder, test_org_id)
        if error_no_ph:
            print(f"Error: {error_no_ph}")
        elif results_no_ph is not None:
            print("Results (query without placeholder - check logs for warning):")
            for row in results_no_ph:
                print(row)

    print("\nBigQuery service test finished.")
