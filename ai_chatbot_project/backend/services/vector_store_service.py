import chromadb
import os
import json
import google.generativeai as genai
from backend.config import settings
import logging
from sentence_transformers import SentenceTransformer # Fallback

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Schema definition (same as in llm_service.py, consider moving to a shared location)
SCHEMA_JSON = """
{
    "table_name": "mrt_events",
    "description": "Captures data related to event enrollments and registrations. Each record represents a unique enrollment of a user into an event organized by a specific organization. so there can be multiple enrollments to the same event or event the same user with multiple enrollments to different events",
    "columns": [
      { "name": "organization_name", "type": "STRING", "description": "The name of the organization hosting the event." },
      { "name": "organization_id", "type": "STRING", "description": "A unique identifier for the organization hosting the event. Used for filtering data by organization." },
      { "name": "organization_category", "type": "STRING", "description": "The category of the organization. Possible values: 'hospital', 'NGO', 'pharma', 'association'." },
      { "name": "event_title", "type": "STRING", "description": "The title or name of the event." },
      { "name": "event_id", "type": "STRING", "description": "A unique identifier for the event." },
      { "name": "event_status", "type": "STRING", "description": "The current status of the event. Possible values: 'published', 'draft'." },
      { "name": "event_duration", "type": "INTEGER", "description": "The total duration of the event in minutes." },
      { "name": "attendance_mode", "type": "STRING", "description": "The mode in which the event is attended. Possible values: 'webinar', 'hybrid', 'self-paced', 'in-person'." },
      { "name": "event_created_at", "type": "TIMESTAMP", "description": "The timestamp when the event was created." },
      { "name": "attendee_id", "type": "STRING", "description": "A unique identifier for the attendee." },
      { "name": "first_name", "type": "STRING", "description": "The first name of the attendee." },
      { "name": "last_name", "type": "STRING", "description": "The last name of the attendee." },
      { "name": "email", "type": "STRING", "description": "The email address of the attendee." },
      { "name": "phone_number", "type": "STRING", "description": "The phone number of the attendee." },
      { "name": "gender", "type": "STRING", "description": "The gender of the attendee." },
      { "name": "county", "type": "STRING", "description": "The county or regional area where the attendee is located." },
      { "name": "country", "type": "STRING", "description": "The country where the attendee is located." },
      { "name": "registration_number", "type": "STRING", "description": "A unique registration number assigned to the attendee." },
      { "name": "profession", "type": "STRING", "description": "The profession or cadre of the attendee (e.g., healthcare professionals like Doctor, Nurse)." },
      { "name": "job_title", "type": "STRING", "description": "The specific job title of the attendee." },
      { "name": "workplace", "type": "STRING", "description": "The name of the organization or institution where the attendee works." },
      { "name": "location", "type": "STRING", "description": "The specific location or address of the attendee's workplace or residence." },
      { "name": "ward", "type": "STRING", "description": "The ward or sub-region within the county where the attendee is located." },
      { "name": "department", "type": "STRING", "description": "The department or unit within the attendee's workplace." },
      { "name": "branch", "type": "STRING", "description": "The branch or division of the attendee's workplace." },
      { "name": "enrollment_id", "type": "STRING", "description": "A unique identifier for each enrollment into an event." },
      { "name": "Attendee_Duration", "type": "INTEGER", "description": "The duration in minutes that the attendee spent attending the event." },
      { "name": "attended", "type": "BOOLEAN", "description": "Whether the attendee attended the event. True means attended, False means did not attend." },
      { "name": "registration_time", "type": "TIMESTAMP", "description": "The timestamp when the attendee registered for the event." }
    ]
  }
"""

CHROMA_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "chroma_db_store"))
SCHEMA_COLLECTION_NAME = "mrt_events_schema"

# Initialize ChromaDB client
if not os.path.exists(CHROMA_DB_PATH):
    os.makedirs(CHROMA_DB_PATH)
    logger.info(f"ChromaDB path created at: {CHROMA_DB_PATH}")

client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
sentence_transformer_model = None # Global variable for fallback model

def get_gemini_embeddings(texts: list[str]) -> list[list[float]] | None:
    if not settings.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not found in settings. Cannot generate embeddings.")
        return None
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        # Check available models for embedding
        # for m in genai.list_models():
        #     if 'embedContent' in m.supported_generation_methods:
        #         print(m.name) # e.g., models/embedding-001, models/text-embedding-004
        
        # Using a known embedding model name. Replace if a different one is preferred/available.
        embedding_model_name = "models/text-embedding-004" # Or "models/embedding-001"
        
        result = genai.embed_content(
            model=embedding_model_name,
            content=texts,
            task_type="RETRIEVAL_DOCUMENT" # or "SEMANTIC_SIMILARITY" / "RETRIEVAL_QUERY"
        )
        return result['embedding']
    except Exception as e:
        logger.error(f"Error generating Gemini embeddings: {e}", exc_info=True)
        return None

def get_st_embeddings(texts: list[str]) -> list[list[float]] | None:
    global sentence_transformer_model
    logger.warning("Using fallback SentenceTransformer for embeddings.")
    try:
        if sentence_transformer_model is None:
            sentence_transformer_model = SentenceTransformer('all-MiniLM-L6-v2')
        embeddings = sentence_transformer_model.encode(texts, show_progress_bar=False)
        return embeddings.tolist() # Convert numpy array to list of lists
    except Exception as e:
        logger.error(f"Error generating SentenceTransformer embeddings: {e}", exc_info=True)
        return None

# Choose embedding function: prioritize Gemini
EMBEDDING_FUNCTION_TO_USE = get_gemini_embeddings
# Uncomment below to force fallback for testing if Gemini is not working
# EMBEDDING_FUNCTION_TO_USE = get_st_embeddings
# logger.warning("FORCED FALLBACK TO SENTENCE TRANSFORMER EMBEDDINGS FOR TESTING.")


def initialize_schema_vector_db():
    logger.info(f"Initializing schema vector database. Collection name: {SCHEMA_COLLECTION_NAME}")
    try:
        collection = client.get_or_create_collection(name=SCHEMA_COLLECTION_NAME)
        
        if collection.count() > 0:
            logger.info(f"Collection '{SCHEMA_COLLECTION_NAME}' already populated with {collection.count()} documents. Skipping initialization.")
            return

        logger.info("Parsing schema and preparing documents for embedding...")
        schema_data = json.loads(SCHEMA_JSON)
        table_name = schema_data.get("table_name", "unknown_table")
        table_description = schema_data.get("description", "")

        documents = []
        metadatas = []
        ids = []

        # Add table description
        doc_id_table = f"table_{table_name}"
        if table_description:
            documents.append(f"Table: {table_name}. Description: {table_description}")
            metadatas.append({"table": table_name, "type": "table_description"})
            ids.append(doc_id_table)

        # Add column information
        for col in schema_data.get("columns", []):
            col_name = col.get("name")
            col_type = col.get("type")
            col_description = col.get("description")
            
            if not col_name or not col_type:
                logger.warning(f"Skipping column due to missing name or type: {col}")
                continue

            doc_id_col = f"table_{table_name}_col_{col_name}"
            doc_text = f"Table: {table_name}. Column: {col_name} (Type: {col_type})."
            if col_description:
                doc_text += f" Description: {col_description}"
            
            documents.append(doc_text)
            metadatas.append({"table": table_name, "column": col_name, "type": "column_info"})
            ids.append(doc_id_col)

        if not documents:
            logger.warning("No documents generated from schema. Vector DB will be empty.")
            return

        logger.info(f"Generating embeddings for {len(documents)} schema documents...")
        embeddings = EMBEDDING_FUNCTION_TO_USE(documents)

        if embeddings is None or len(embeddings) != len(documents):
            logger.error("Failed to generate embeddings or mismatch in embedding count. Aborting DB initialization.")
            # Potentially try fallback if Gemini failed and it wasn't already the fallback
            if EMBEDDING_FUNCTION_TO_USE == get_gemini_embeddings:
                logger.info("Attempting fallback to SentenceTransformer embeddings...")
                embeddings = get_st_embeddings(documents)
                if embeddings is None or len(embeddings) != len(documents):
                    logger.error("Fallback SentenceTransformer embeddings also failed. Aborting DB initialization.")
                    return
            else: # Already tried fallback or it was the primary
                return


        logger.info(f"Adding {len(documents)} documents to ChromaDB collection '{SCHEMA_COLLECTION_NAME}'.")
        collection.add(
            documents=documents,
            embeddings=embeddings, # type: ignore
            metadatas=metadatas, # type: ignore
            ids=ids
        )
        logger.info("Successfully initialized and populated schema vector database.")

    except Exception as e:
        logger.error(f"Error initializing schema vector database: {e}", exc_info=True)

def query_schema(user_query: str, n_results: int = 5) -> list[str]:
    logger.info(f"Querying schema vector database with query: '{user_query}', n_results={n_results}")
    try:
        collection = client.get_collection(name=SCHEMA_COLLECTION_NAME) # Assumes collection exists
        
        query_embedding = EMBEDDING_FUNCTION_TO_USE([user_query])
        if query_embedding is None or not query_embedding:
            logger.error("Failed to generate embedding for the user query.")
            return []

        results = collection.query(
            query_embeddings=query_embedding, # type: ignore
            n_results=n_results
        )
        
        # The 'documents' key might be a list of lists, depending on the query.
        # We expect one query embedding, so one list of document results.
        retrieved_docs = results.get('documents', [[]])[0]
        
        logger.info(f"Retrieved {len(retrieved_docs)} documents from vector store: {retrieved_docs}")
        return retrieved_docs
    
    except chromadb.errors.CollectionNotFoundError:
        logger.error(f"ChromaDB collection '{SCHEMA_COLLECTION_NAME}' not found during query. Was it initialized?")
        return []
    except Exception as e:
        logger.error(f"Error querying schema vector database: {e}", exc_info=True)
        return []

# Initialize the DB when the module is loaded.
# This is generally okay for smaller, specific-purpose vector stores.
# For larger applications, you might manage initialization explicitly at app startup.
if __name__ == '__main__':
    print("Running vector_store_service.py directly for testing...")
    print(f"ChromaDB path: {CHROMA_DB_PATH}")

    # Test initialization
    print("\n--- Testing DB Initialization ---")
    initialize_schema_vector_db()
    
    # Verify collection count
    try:
        collection = client.get_collection(name=SCHEMA_COLLECTION_NAME)
        print(f"Collection '{SCHEMA_COLLECTION_NAME}' count: {collection.count()}")
        # Peek at a few items if needed
        # print(collection.peek(limit=2))
    except Exception as e:
        print(f"Error accessing collection after init: {e}")


    # Test querying
    print("\n--- Testing Schema Querying ---")
    if settings.GEMINI_API_KEY or EMBEDDING_FUNCTION_TO_USE == get_st_embeddings: # Ensure API key for Gemini or ST is chosen
        test_queries = [
            "What events are there?",
            "Tell me about attendee professions.",
            "Details about event duration and status."
        ]
        for tq in test_queries:
            print(f"\nQuerying for: '{tq}'")
            retrieved_parts = query_schema(tq, n_results=3)
            if retrieved_parts:
                for i, part in enumerate(retrieved_parts):
                    print(f"  Result {i+1}: {part}")
            else:
                print("  No relevant schema parts found.")
    else:
        print("Skipping query tests as GEMINI_API_KEY is not set and SentenceTransformer is not forced.")
    
    print("\nvector_store_service.py test run complete.")
else:
    # This will run when the module is imported by another part of the application (e.g., main.py or llm_service.py)
    logger.info("vector_store_service module loaded. Attempting to initialize schema vector DB...")
    initialize_schema_vector_db()
