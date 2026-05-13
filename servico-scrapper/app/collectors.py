import random
from datetime import datetime

_HEADLINES = [
    "Safra 2025 de café arábica supera expectativas no Sul de Minas",
    "Exportações de café do Brasil crescem 12% no primeiro semestre",
    "Geada atípica ameaça lavouras cafeeiras em Minas Gerais",
    "Preço do café no mercado internacional bate máxima do ano",
    "Consumo interno de café no Brasil cresce pelo quinto ano seguido",
    "Novas variedades resistentes à ferrugem ganham espaço no Cerrado",
    "Cooperativas investem em rastreabilidade para mercado de cafés especiais",
    "Vietnã reduz produção e eleva demanda por café brasileiro",
]

_CONDITIONS = ["Ensolarado", "Parcialmente nublado", "Nublado", "Chuva leve"]


def collect_noticias() -> list[dict]:
    headlines = random.sample(_HEADLINES, k=2)
    now = datetime.utcnow().isoformat()
    return [
        {
            "tipo": "noticia",
            "titulo": h,
            "coletado_em": now,
            "fonte": "mock",
        }
        for h in headlines
    ]


def collect_clima() -> dict:
    return {
        "tipo": "clima",
        "cidade": "Lavras-MG",
        "temperatura_c": round(random.uniform(15.0, 30.0), 1),
        "umidade_pct": random.randint(45, 95),
        "condicao": random.choice(_CONDITIONS),
        "coletado_em": datetime.utcnow().isoformat(),
        "fonte": "mock",
    }


def collect_cotacao() -> dict:
    return {
        "tipo": "cotacao",
        "produto": "cafe_arabica",
        "preco_usc_lb": round(random.uniform(200.0, 300.0), 2),
        "coletado_em": datetime.utcnow().isoformat(),
        "fonte": "mock",
    }


def run_cycle() -> list[dict]:
    messages = []
    messages.extend(collect_noticias())
    messages.append(collect_clima())
    messages.append(collect_cotacao())
    return messages
