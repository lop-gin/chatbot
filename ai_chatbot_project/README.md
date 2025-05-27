# AI Chatbot for BigQuery Data Visualization

This project is an AI-powered chatbot application designed to allow users to query a BigQuery database using natural language. The chatbot interprets user questions, generates appropriate SQL queries, executes them on BigQuery, and then visualizes the results using charts and provides natural language explanations.

**Key Technologies:**

*   **Frontend:** Next.js (React framework) with TypeScript and Tailwind CSS.
*   **Backend:** FastAPI (Python web framework).
*   **LLM:** Google Gemini (for SQL generation and explanations).
*   **Database:** Google BigQuery.
*   **Charting:** Plotly.
*   **Vector Store (RAG):** ChromaDB with Gemini and SentenceTransformer embeddings for schema retrieval.

## Prerequisites

Before you begin, ensure you have the following installed and configured:

*   **Python:** Version 3.9 or higher.
*   **Node.js:** Version 18.0 or higher (for the frontend).
*   **Google Cloud Platform (GCP) Project:**
    *   Access to a GCP project.
    *   BigQuery API enabled.
    *   Vertex AI API or Generative Language API enabled (for Gemini access).
*   **`gcloud` CLI (Recommended):** For easier authentication and project management.
*   **Service Account:** A GCP service account with appropriate permissions for BigQuery (see Backend Setup).
*   **API Keys:**
    *   **Gemini API Key:** Obtainable from Google AI Studio or your GCP project.

## Directory Structure

The project is organized into two main directories:

*   `/frontend`: Contains the Next.js frontend application.
*   `/backend`: Contains the FastAPI backend application and related services.

## Backend Setup (`ai_chatbot_project/backend`)

1.  **Navigate to Backend Directory:**
    ```bash
    cd ai_chatbot_project/backend
    ```

2.  **Create and Activate Python Virtual Environment:**
    *   On macOS/Linux:
        ```bash
        python3 -m venv venv
        source venv/bin/activate
        ```
    *   On Windows:
        ```bash
        python -m venv venv
        venv\Scripts\activate
        ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Environment Variables:**
    *   Copy the example environment file:
        ```bash
        cp .env.example .env
        ```
    *   Edit the `.env` file and provide the following values:

        *   `GEMINI_API_KEY`: Your API key for the Google Gemini LLM. You can obtain this from [Google AI Studio](https://aistudio.google.com/app/apikey) or your GCP project if using Vertex AI Gemini models.
        *   `BIGQUERY_PROJECT_ID`: The ID of your Google Cloud Project where your BigQuery dataset is located.
        *   `GOOGLE_APPLICATION_CREDENTIALS`: The **absolute path** to your Google Cloud service account JSON key file. This is essential for the backend to authenticate with Google Cloud services, including BigQuery.

5.  **Service Account for BigQuery:**
    *   **Why?** The backend application needs to authenticate with Google Cloud to interact with your BigQuery data. A service account provides dedicated credentials for this purpose.
    *   **Create/Select a Service Account:**
        1.  Go to the "IAM & Admin" > "Service Accounts" page in the GCP Console.
        2.  You can use an existing service account or create a new one.
    *   **Grant Permissions:** Assign the following roles to your service account for the project containing your BigQuery data:
        *   `BigQuery Data Viewer`: Allows reading data from BigQuery tables.
        *   `BigQuery Job User` (or `BigQuery User`): Allows running queries (jobs) in BigQuery.
    *   **Download JSON Key:**
        1.  After creating/selecting the service account, go to its "Keys" tab.
        2.  Click "Add Key" > "Create new key".
        3.  Choose "JSON" as the key type and click "Create".
        4.  A JSON file will be downloaded. **Store this file securely.**
        5.  Update the `GOOGLE_APPLICATION_CREDENTIALS` in your `.env` file with the absolute path to this downloaded JSON key.

6.  **Running the Backend:**
    The schema vector database (ChromaDB) will be initialized automatically when the backend starts (if not already populated).
    ```bash
    # Ensure you are in the ai_chatbot_project/backend directory
    # and your virtual environment is activated.
    uvicorn main:app --reload --port 8000
    ```
    Alternatively, you can run `python main.py` if Uvicorn is configured to run directly from the script (though `uvicorn main:app` is standard for FastAPI).

## Frontend Setup (`ai_chatbot_project/frontend`)

1.  **Navigate to Frontend Directory:**
    ```bash
    cd ai_chatbot_project/frontend
    ```
    (If you were in the `backend` directory, use `cd ../frontend`)

2.  **Install Dependencies:**
    ```bash
    npm install
    ```

3.  **Running the Frontend:**
    ```bash
    npm run dev
    ```

## Accessing the Application

Once both the backend and frontend are running:

*   Open your web browser and navigate to: `http://localhost:3000`

## How it Works

1.  **User Input:** The user types a natural language query into the chat interface in the Next.js frontend.
2.  **API Request:** The frontend sends this query to the FastAPI backend (`/api/chat` endpoint).
3.  **Backend Processing:**
    *   **Schema Retrieval (RAG):** The `llm_service` queries the `vector_store_service` (ChromaDB). The vector store, pre-populated with embeddings of the BigQuery table schema, returns relevant schema parts (table descriptions, column names, types, and descriptions) based on the user's query. This uses Gemini embeddings by default, with a fallback to SentenceTransformer embeddings.
    *   **SQL Generation:** The `llm_service` uses the Google Gemini LLM, providing the user's query and the retrieved contextual schema parts, to generate a BigQuery-compatible SQL query.
    *   **BigQuery Execution:** The `bigquery_service` executes the generated SQL query against your BigQuery database.
    *   **Chart Generation:** If data is returned, the `chart_service` uses Plotly to generate an interactive chart (e.g., bar, line, histogram based on query and data). The chart is saved as an HTML file in the `backend/static` directory.
    *   **Explanation Generation:** The `llm_service` uses the Google Gemini LLM again, this time providing the original user query, the generated SQL, and a sample of the data (or a "no data" message) to generate a natural language explanation of the results.
4.  **API Response:** The backend sends a JSON response to the frontend containing:
    *   The generated SQL query.
    *   The data retrieved from BigQuery (if any).
    *   The natural language explanation.
    *   A URL to the generated chart (if any).
5.  **Display Results:** The Next.js frontend receives the response and dynamically displays the explanation, SQL query, data table, and the interactive chart (loaded in an iframe).

## Bonus Features

*   **SQL Explanation Endpoint (`/api/explain-sql`):**
    *   A separate backend endpoint that accepts an SQL query string.
    *   Uses the Gemini LLM to provide a detailed explanation of the provided SQL query's functionality.

---

This README provides a comprehensive guide to setting up and running the application. Ensure all API keys and service account details are handled securely and are not committed to version control.
