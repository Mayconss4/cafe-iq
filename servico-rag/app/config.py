import os

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
CHROMA_HOST = os.getenv("CHROMA_HOST", "chromadb")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "cafeiq")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
RETRIEVER_K = int(os.getenv("RETRIEVER_K", "4"))

MCP_URL = os.getenv("MCP_URL", "http://servico-mcp:8002")

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "event-bus")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "cafeiq")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "cafeiq123")
QUEUE_NAME = os.getenv("QUEUE_NAME", "cafeiq.ingestao")
CONSUMER_RETRY_DELAY = int(os.getenv("CONSUMER_RETRY_DELAY", "5"))
