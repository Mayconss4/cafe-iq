import os

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "event-bus")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "cafeiq")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "cafeiq123")
QUEUE_NAME = os.getenv("QUEUE_NAME", "cafeiq.ingestao")
COLLECT_INTERVAL = int(os.getenv("COLLECT_INTERVAL", "60"))
