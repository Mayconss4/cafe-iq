import json
import logging
import threading
import time

import pika
import pika.exceptions

from app.config import (
    RABBITMQ_HOST,
    RABBITMQ_PORT,
    RABBITMQ_USER,
    RABBITMQ_PASS,
    QUEUE_NAME,
    CONSUMER_RETRY_DELAY,
)
from app.rag import ingest_document

log = logging.getLogger(__name__)


def _build_ingest_args(msg: dict) -> tuple[str, str] | None:
    """Map a scrapper message to (texto, fonte) for ingest_document, or None to skip."""
    tipo = msg.get("tipo")

    if tipo == "noticia":
        titulo = msg.get("titulo", "").strip()
        if not titulo:
            return None
        return titulo, f"scrapper/noticia"

    if tipo == "clima":
        cidade = msg.get("cidade", "desconhecida")
        texto = (
            f"Clima em {cidade}: {msg.get('temperatura_c')}°C, "
            f"umidade {msg.get('umidade_pct')}%, {msg.get('condicao')}."
        )
        return texto, "scrapper/clima"

    if tipo == "cotacao":
        produto = msg.get("produto", "cafe")
        preco = msg.get("preco_usc_lb")
        texto = f"Cotação {produto}: {preco} USc/lb em {msg.get('coletado_em', '')}."
        return texto, "scrapper/cotacao"

    log.warning("Tipo de mensagem desconhecido: %s — ignorando.", tipo)
    return None


def _on_message(channel, method, _properties, body: bytes) -> None:
    try:
        msg = json.loads(body.decode())
    except json.JSONDecodeError as exc:
        log.error("Mensagem inválida (não é JSON): %s", exc)
        channel.basic_ack(delivery_tag=method.delivery_tag)
        return

    args = _build_ingest_args(msg)
    if args is None:
        channel.basic_ack(delivery_tag=method.delivery_tag)
        return

    texto, fonte = args
    try:
        doc_id = ingest_document(texto, fonte)
        log.info("Indexado [%s] id=%s fonte=%s", msg.get("tipo"), doc_id, fonte)
        channel.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as exc:
        # nack without requeue so the message doesn't loop forever on persistent errors
        log.error("Falha ao indexar mensagem: %s", exc)
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def _consume_loop() -> None:
    """Blocking consume loop with auto-reconnect. Intended to run in a daemon thread."""
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    params = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=credentials,
        heartbeat=60,
        blocked_connection_timeout=30,
    )

    while True:
        try:
            log.info("Conectando ao RabbitMQ em %s:%s…", RABBITMQ_HOST, RABBITMQ_PORT)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE_NAME, durable=True)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=QUEUE_NAME, on_message_callback=_on_message)

            log.info("Consumer aguardando mensagens na fila '%s'.", QUEUE_NAME)
            channel.start_consuming()

        except pika.exceptions.AMQPConnectionError as exc:
            log.warning("Conexão perdida: %s. Reconectando em %ds…", exc, CONSUMER_RETRY_DELAY)
        except Exception as exc:
            log.error("Erro inesperado no consumer: %s. Reconectando em %ds…", exc, CONSUMER_RETRY_DELAY)

        time.sleep(CONSUMER_RETRY_DELAY)


def start_consumer_thread() -> threading.Thread:
    thread = threading.Thread(target=_consume_loop, name="rabbitmq-consumer", daemon=True)
    thread.start()
    log.info("Thread consumer iniciada (id=%s).", thread.ident)
    return thread
