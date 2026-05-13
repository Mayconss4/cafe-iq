import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.collectors import run_cycle
from app.config import COLLECT_INTERVAL
from app.publisher import Publisher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("scrapper")

# Setting this event skips the current sleep and triggers an immediate cycle.
_manual_trigger = threading.Event()
_publisher: Publisher | None = None


def _collect_loop() -> None:
    global _publisher
    _publisher = Publisher()
    log.info("Loop de coleta iniciado. Intervalo: %ds", COLLECT_INTERVAL)

    while True:
        log.info("Iniciando ciclo de coleta…")
        messages = run_cycle()
        published = _publisher.publish_many(messages)
        log.info("Ciclo concluído — %d/%d mensagens publicadas.", published, len(messages))

        # Wait for the interval or until a manual trigger wakes us up early.
        triggered = _manual_trigger.wait(timeout=COLLECT_INTERVAL)
        if triggered:
            log.info("Coleta manual solicitada — iniciando ciclo imediato.")
        _manual_trigger.clear()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    thread = threading.Thread(target=_collect_loop, name="collect-loop", daemon=True)
    thread.start()
    yield


app = FastAPI(title="servico-scrapper", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/coletar-agora")
def coletar_agora():
    _manual_trigger.set()
    return {"mensagem": "Coleta manual disparada.", "ok": True}
