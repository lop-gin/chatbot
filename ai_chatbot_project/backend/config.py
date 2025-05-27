import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") # Removed/Commented out
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    BIGQUERY_PROJECT_ID = os.getenv("BIGQUERY_PROJECT_ID")
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

settings = Settings()
