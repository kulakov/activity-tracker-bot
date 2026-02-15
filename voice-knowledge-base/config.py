import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("VKB_TELEGRAM_TOKEN", "")

# LLM Backend: "anthropic" | "ollama" | "claude-cli"
LLM_BACKEND = os.getenv("VKB_LLM_BACKEND", "anthropic")

# Anthropic API
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("VKB_ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

# Ollama
OLLAMA_BASE_URL = os.getenv("VKB_OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("VKB_OLLAMA_MODEL", "llama3.1")

# Whisper STT
WHISPER_MODEL = os.getenv("VKB_WHISPER_MODEL", "medium")
WHISPER_DEVICE = os.getenv("VKB_WHISPER_DEVICE", "auto")

# TTS
TTS_VOICE = os.getenv("VKB_TTS_VOICE", "ru-RU-DmitryNeural")
TTS_RATE = os.getenv("VKB_TTS_RATE", "+0%")

# Knowledge Base
KB_PERSIST_DIR = os.getenv("VKB_KB_DIR", "./kb_data")
EMBEDDING_MODEL = os.getenv("VKB_EMBEDDING_MODEL", "intfloat/multilingual-e5-base")
CHUNK_SIZE = int(os.getenv("VKB_CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("VKB_CHUNK_OVERLAP", "200"))
TOP_K_RESULTS = int(os.getenv("VKB_TOP_K", "5"))

# Conversation
MAX_HISTORY_MESSAGES = int(os.getenv("VKB_MAX_HISTORY", "20"))

SYSTEM_PROMPT = os.getenv("VKB_SYSTEM_PROMPT", (
    "You are a knowledgeable assistant that helps discuss projects and ideas. "
    "You have access to a knowledge base with project documentation and notes. "
    "Use the provided context to give informed, detailed answers. "
    "Respond in the same language as the user's question. "
    "Be conversational and helpful, as if discussing with a colleague."
))
