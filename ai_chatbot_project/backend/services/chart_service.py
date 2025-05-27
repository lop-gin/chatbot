import plotly.express as px
import plotly.io as pio
import os
import uuid
import logging
from typing import List, Dict, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Path to the static directory: ai_chatbot_project/backend/static
# __file__ is ai_chatbot_project/backend/services/chart_service.py
# os.path.dirname(__file__) is ai_chatbot_project/backend/services
# os.path.join(os.path.dirname(__file__), "..", "static") navigates up to backend then to static
STATIC_DIR_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))

# Ensure 'backend/static' directory exists at startup of this module
if not os.path.exists(STATIC_DIR_PATH):
    try:
        os.makedirs(STATIC_DIR_PATH)
        logger.info(f"Successfully created static directory at: {STATIC_DIR_PATH}")
    except OSError as e:
        logger.error(f"Failed to create static directory at {STATIC_DIR_PATH} on module load: {e}", exc_info=True)
        # This is a critical error for chart saving. Depending on requirements,
        # this could raise an exception to halt startup or proceed without chart functionality.
        # For now, we log and proceed; generate_chart_html will handle the missing dir.

def generate_chart_html(data: List[Dict], query: str) -> Optional[str]:
    """
    Generates a chart from the given data and query, saves it as an HTML file,
    and returns the static URL path to the chart.

    Args:
        data: A list of dictionaries representing the data to plot.
        query: The user query, used to infer chart type and for titles.

    Returns:
        A string representing the static URL path (e.g., /static/chart_uuid.html)
        or None if chart generation fails or is not applicable.
    """
    if not data:
        logger.info("No data provided, cannot generate chart.")
        return None

    if not os.path.exists(STATIC_DIR_PATH):
        logger.error(f"Static directory does not exist at {STATIC_DIR_PATH}. Cannot save chart. "
                     "This should have been created at module load or by main.py.")
        # Attempt to create it again, just in case.
        try:
            os.makedirs(STATIC_DIR_PATH)
            logger.info(f"Retry: Successfully created static directory at: {STATIC_DIR_PATH}")
        except OSError as e:
            logger.error(f"Retry: Failed to create static directory at {STATIC_DIR_PATH}: {e}", exc_info=True)
            return None # Critical failure

    chart_type = None
    x_col, y_col = None, None
    title = "Chart" # Default title

    if len(data) > 0 and isinstance(data[0], dict) and len(data[0].keys()) >= 1:
        keys = list(data[0].keys())
        query_lower = query.lower()

        # Attempt to find a numeric column for y-axis and a string/categorical for x-axis
        numeric_cols = [k for k, v in data[0].items() if isinstance(v, (int, float))]
        string_cols = [k for k, v in data[0].items() if isinstance(v, str)]

        if len(keys) == 1 and numeric_cols: # Single numeric column -> histogram
            x_col = numeric_cols[0]
            chart_type = "histogram"
            title = f"Distribution of {x_col}"
        elif len(numeric_cols) >= 1 and len(string_cols) >=1 : # At least one numeric and one string
            y_col = numeric_cols[0] # Default to first numeric column for y-axis
            x_col = string_cols[0]  # Default to first string column for x-axis
            
            if "distribution" in query_lower or "count by" in query_lower or \
               "group by" in query_lower or "average of" in query_lower or "sum of" in query_lower:
                chart_type = "bar"
                title = f"{y_col} by {x_col}"
            elif "trend" in query_lower or "over time" in query_lower:
                chart_type = "line"
                title = f"{y_col} over {x_col}"
            else: # Default to bar if specific keywords not found but suitable columns exist
                chart_type = "bar"
                title = f"{y_col} by {x_col}"

        elif len(numeric_cols) >= 2 : # If multiple numeric columns and no clear string column for x
            # Could be a scatter plot, or bar chart if one is clearly a "count" or "value"
             y_col = numeric_cols[0]
             x_col = numeric_cols[1] # This might not always make sense
             if "scatter" in query_lower or "correlation" in query_lower:
                 chart_type = "scatter"
                 title = f"Scatter plot of {y_col} vs {x_col}"
             else: # Default to bar using the first two numeric cols
                 chart_type = "bar" 
                 title = f"{y_col} by {x_col}"


    if not chart_type or not x_col: # x_col is essential for most charts
        logger.info(f"Could not determine a suitable chart type or x_col for the query: '{query}' and data structure.")
        return None

    fig = None
    try:
        logger.info(f"Attempting to generate '{chart_type}' chart. X='{x_col}', Y='{y_col if y_col else 'N/A'}'. Title='{title}'")
        if chart_type == "bar":
            if y_col: # y_col is required for bar chart
                fig = px.bar(data, x=x_col, y=y_col, title=title)
            else:
                logger.warning(f"Cannot generate bar chart: y_col is missing for x_col '{x_col}'.")
                return None
        elif chart_type == "line":
            if y_col: # y_col is required for line chart
                fig = px.line(data, x=x_col, y=y_col, title=title)
            else:
                logger.warning(f"Cannot generate line chart: y_col is missing for x_col '{x_col}'.")
                return None
        elif chart_type == "histogram":
             # y_col is not used for px.histogram when x is specified
            fig = px.histogram(data, x=x_col, title=title)
        elif chart_type == "scatter":
            if y_col: # y_col is required for scatter
                fig = px.scatter(data, x=x_col, y=y_col, title=title)
            else:
                logger.warning(f"Cannot generate scatter plot: y_col is missing for x_col '{x_col}'.")

        if fig is None:
            logger.info("Plotly figure was not generated.")
            return None

        filename = f"chart_{uuid.uuid4().hex}.html"
        # STATIC_DIR_PATH is an absolute path to 'ai_chatbot_project/backend/static'
        chart_filepath = os.path.join(STATIC_DIR_PATH, filename)
        
        logger.info(f"Saving chart to: {chart_filepath}")
        pio.write_html(fig, file=chart_filepath, auto_open=False, full_html=True, include_plotlyjs='cdn')
        logger.info(f"Successfully saved chart: {filename}")
        
        return f"/static/{filename}" # URL path for frontend to access

    except Exception as e:
        logger.error(f"Error generating or saving chart (type: {chart_type}, x: {x_col}, y: {y_col}): {e}", exc_info=True)
        return None

if __name__ == '__main__':
    print("Starting chart_service.py test...")
    
    # Test data
    sample_data_bar = [{'category': 'A', 'value': 30}, {'category': 'B', 'value': 50}]
    sample_data_line = [{'date': '2023-01-01', 'metric': 100}, {'date': '2023-01-02', 'metric': 120}]
    sample_data_hist = [{'score': 85} for _ in range(10)] + [{'score': 90} for _ in range(5)]
    sample_data_scatter = [{'x_val': i, 'y_val': i*i + uuid.uuid4().int % 10} for i in range(10)]


    print("\nTesting Bar Chart (count by category):")
    chart_url = generate_chart_html(sample_data_bar, "show count by category")
    print(f"Chart URL: {chart_url}" if chart_url else "Chart generation failed.")
    if chart_url: print(f"  Expected file at: {STATIC_DIR_PATH}{chart_url.replace('/static', '')}")


    print("\nTesting Line Chart (metric over time):")
    chart_url = generate_chart_html(sample_data_line, "show metric over time")
    print(f"Chart URL: {chart_url}" if chart_url else "Chart generation failed.")

    print("\nTesting Histogram (distribution of score):")
    chart_url = generate_chart_html(sample_data_hist, "show distribution of score")
    print(f"Chart URL: {chart_url}" if chart_url else "Chart generation failed.")

    print("\nTesting Scatter Plot (y_val vs x_val):")
    chart_url = generate_chart_html(sample_data_scatter, "show correlation of y_val vs x_val")
    print(f"Chart URL: {chart_url}" if chart_url else "Chart generation failed.")

    print("\nTesting with empty data:")
    chart_url = generate_chart_html([], "any query")
    print(f"Chart URL: {chart_url}" if chart_url else "Chart generation appropriately failed for empty data.")

    print("\nTesting with unsuitable data (single non-numeric column):")
    chart_url = generate_chart_html([{'name': 'alpha'}, {'name':'beta'}], "any query")
    print(f"Chart URL: {chart_url}" if chart_url else "Chart generation appropriately failed for unsuitable data.")
    
    print("\nchart_service.py test finished.")
