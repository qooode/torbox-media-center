import os
from dotenv import load_dotenv

load_dotenv()

# These values are optional; OpenRouter naming is only enabled when an API key is provided.
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "x-ai/grok-4-fast")
