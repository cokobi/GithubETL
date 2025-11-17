import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy import text
import logging

#loead environment variables from .env file
load_dotenv()

# --- Logging Configuration ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR = os.getenv("LOG_DIR", "logs")
LOG_FILE = os.path.join(LOG_DIR, "etl.log")
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'

# --- GitHub API Configuration ---
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
BASE_URL = "https://api.github.com/search/repositories"

def get_github_headers():
    """
    Creates the authorization headers for the GitHub API.
    """
    if not GITHUB_TOKEN:
        logging.warning("GITHUB_TOKEN not set in .env. API calls will be unauthenticated.")
        return {}
    return {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }

def get_db_engine():
    """
    Creates and returns a SQLAlchemy Engine based on environment variables.
    """
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASS")
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")

    if not all([user, password, host, port, db_name]):
        raise ValueError('Can\'t connect to DB. Set up .env vars: DB_USER, DB_PASS, DB_HOST, DB_PORT, DB_NAME.')
    
    db_url = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"

    try:
        engine = create_engine(db_url)
        #test connection:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1")) 
        logging.info("Database connection established successfully.")
        return engine
    except Exception as e:
        logging.error(f"Failed to create database engine: {e}", exc_info=True)
        raise