import json
import logging
import time

import pika
import pika.exceptions

from app.config import (
    RABBITMQ_HOST,
    RABBITMQ_PORT,
    RABBITMQ_USER,
    RABBITMQ_PASS,
    QUEUE_NAME,
)

log = logging.getLogger(__name__)

_RETRY_DELAYS = [5, 10, 30]  # seconds between reconnect attempts


def _credentials() -> pika.PlainCredentials:
    return pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)


def _connect() -> pika.BlockingConnection:
    params = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=_credentials(),
        heartbeat=60,
        blocked_connection_timeout=30,
    )
    for attempt, delay in enumerate(_RETRY_DELAYS, start=1):
        try:
            conn = pika.BlockingConnection(params)
            log.info("Conectado ao RabbitMQ em %s:%s", RABBITMQ_HOST, RABBITMQ_PORT)
            return conn
        except pika.exceptions.AMQPConnectionError as exc:
            log.warning("Tentativa %d falhou: %s. Aguardando %ds…", attempt, exc, delay)
            time.sleep(delay)
    # Final attempt — let the exception propagate
    return pika.BlockingConnection(params)


class Publisher:
    def __init__(self) -> None:
        self._conn: pika.BlockingConnection | None = None
        self._channel: pika.adapters.blocking_connection.BlockingChannel | None = None

    def _ensure_connected(self) -> None:
        if self._conn and self._conn.is_open:
            return
        self._conn = _connect()
        self._channel = self._conn.channel()
        self._channel.queue_declare(queue=QUEUE_NAME, durable=True)

    def publish(self, message: dict) -> None:
        self._ensure_connected()
        body = json.dumps(message, ensure_ascii=False)
        self._channel.basic_publish(
            exchange="",
            routing_key=QUEUE_NAME,
            body=body.encode(),
            properties=pika.BasicProperties(
                delivery_mode=pika.DeliveryMode.Persistent,
                content_type="application/json",
            ),
        )
        log.debug("Publicado [%s]: %s", message.get("tipo"), body[:120])

    def publish_many(self, messages: list[dict]) -> int:
        published = 0
        for msg in messages:
            try:
                self.publish(msg)
                published += 1
            except Exception as exc:
                log.error("Falha ao publicar mensagem: %s", exc)
                self._conn = None  # force reconnect on next call
        return published

    def close(self) -> None:
        if self._conn and self._conn.is_open:
            self._conn.close()
