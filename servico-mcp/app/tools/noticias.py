import random
from datetime import date, timedelta


_HEADLINES = [
    "Exportações brasileiras de café atingem recorde no trimestre",
    "Geada no Sul de Minas preocupa produtores da safra 2025",
    "ICE Arabica recua após dados de estoques acima do esperado",
    "Conilon ganha espaço no mercado de blends especiais",
    "Brasil mantém liderança mundial na produção de café pelo 25º ano consecutivo",
    "Preços do café robusta sobem com queda na produção do Vietnã",
    "Startup lança plataforma de rastreabilidade de café via blockchain",
    "Cooperativas mineiras investem em secagem mecânica para reduzir perdas",
    "Relatório USDA projeta safra 2025/26 com 68 milhões de sacas",
    "Índia aumenta exportações e pressiona preços no mercado asiático",
]


def run(_params: dict) -> list[dict]:
    today = date.today()
    sample = random.sample(_HEADLINES, k=3)
    return [
        {
            "titulo": headline,
            "data": (today - timedelta(days=i)).isoformat(),
            "fonte": "mock — substituir por API de notícias",
        }
        for i, headline in enumerate(sample)
    ]
