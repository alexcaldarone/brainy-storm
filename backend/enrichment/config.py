import os
from pathlib import Path
from dotenv import load_dotenv

# Paths
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
IDEAS_FILE = DATA_DIR / "ideas.json"
TRANSCRIPT_FILE = DATA_DIR / "transcript.txt"

# Keep local development predictable: `cp .env.example .env` works whether
# uvicorn is launched from the repository root or this service directory.
load_dotenv(PROJECT_ROOT / ".env")

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# LLM Configurations
DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER", "auto")  # "gemini", "openai", "auto", "mock"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Microservice Server Config
SERVER_HOST = os.getenv("ENRICHMENT_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("ENRICHMENT_PORT", "8001"))
