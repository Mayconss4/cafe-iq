# Serviço Scrapper

## Visão geral

Serviço de coleta e publicação de dados simulados sobre o mercado de café. Publica mensagens periodicamente em RabbitMQ para ingestão assíncrona pelo serviço RAG.

- **Linguagem**: Python
- **Framework**: FastAPI
- **Porta**: `8003`
- **Entrypoint**: `servico-scrapper/app/main.py`

## Dependências

```
fastapi==0.111.0
uvicorn[standard]==0.30.1
pika==1.3.2
pydantic==2.7.4
```

## Endpoints

### GET /health

Status do serviço.

**Resposta:**
```json
{
  "status": "ok"
}
```

### POST /coletar-agora

Dispara um ciclo de coleta imediatamente, sem aguardar o intervalo.

**Resposta:**
```json
{
  "mensagem": "Coleta manual disparada.",
  "ok": true
}
```

## Configuração

Via variáveis de ambiente:

| Variável | Padrão | Descrição |
|---|---|---|
| `RABBITMQ_HOST` | `event-bus` | Host do RabbitMQ |
| `RABBITMQ_PORT` | `5672` | Porta do RabbitMQ |
| `RABBITMQ_USER` | `cafeiq` | Usuário RabbitMQ |
| `RABBITMQ_PASS` | `cafeiq123` | Senha RabbitMQ |
| `QUEUE_NAME` | `cafeiq.ingestao` | Nome da fila |
| `COLLECT_INTERVAL` | `60` | Intervalo em segundos entre ciclos |

## Fluxo de coleta

1. **Startup**: inicia thread de coleta daemon
2. **Loop**:
   - Aguarda `COLLECT_INTERVAL` segundos
   - Chama `run_cycle()` para gerar dados
   - Publica cada mensagem em RabbitMQ
   - Registra logs de sucesso/falha
3. **Disparo manual**:
   - `POST /coletar-agora` dispara evento
   - Próximo ciclo ocorre imediatamente (sem aguardar intervalo)

## Dados coletados

### Notícias

- **Tipo**: `noticia`
- **Campo**: `titulo` (selecionado aleatoriamente de lista pré-definida)
- **Exemplo**:
```json
{
  "tipo": "noticia",
  "titulo": "Safra 2025 de café arábica supera expectativas no Sul de Minas",
  "coletado_em": "2025-06-16T14:32:10.123456",
  "fonte": "mock"
}
```
- **Quantidade por ciclo**: 2

### Clima

- **Tipo**: `clima`
- **Campos**:
  - `cidade`: sempre "Lavras-MG" (padrão do domínio)
  - `temperatura_c`: aleatória entre 15.0 e 30.0
  - `umidade_pct`: aleatória entre 45 e 95
  - `condicao`: aleatória (Ensolarado, Parcialmente nublado, Nublado, Chuva leve)
- **Exemplo**:
```json
{
  "tipo": "clima",
  "cidade": "Lavras-MG",
  "temperatura_c": 22.5,
  "umidade_pct": 68,
  "condicao": "Parcialmente nublado",
  "coletado_em": "2025-06-16T14:32:10.654321",
  "fonte": "mock"
}
```
- **Quantidade por ciclo**: 1

### Cotação

- **Tipo**: `cotacao`
- **Campos**:
  - `produto`: sempre "cafe_arabica"
  - `preco_usc_lb`: aleatório entre 200.0 e 300.0
- **Exemplo**:
```json
{
  "tipo": "cotacao",
  "produto": "cafe_arabica",
  "preco_usc_lb": 225.42,
  "coletado_em": "2025-06-16T14:32:10.876543",
  "fonte": "mock"
}
```
- **Quantidade por ciclo**: 1

**Total por ciclo**: 4 mensagens (2 notícias + 1 clima + 1 cotação)

## Estrutura do código

### app/collectors.py

Define funções de coleta:

- `collect_noticias() -> list[dict]`:
  - Amostra 2 manchetes aleatoriamente
  - Retorna lista de dicts com tipo `noticia`

- `collect_clima() -> dict`:
  - Gera temperatura, umidade, condição aleatórios
  - Retorna dict com tipo `clima`

- `collect_cotacao() -> dict`:
  - Gera preço aleatório
  - Retorna dict com tipo `cotacao`

- `run_cycle() -> list[dict]`:
  - Chama as três funções acima
  - Retorna lista com todos os dados

### app/publisher.py

Gerencia conexão e publicação em RabbitMQ:

**Classe `Publisher`:**

- `__init__()`: inicializa com conexão nula
- `_ensure_connected()`: reconnecta se necessário
- `publish(message: dict)`: publica uma mensagem
  - JSON-encoda
  - Usa modo persistente (delivery_mode=Persistent)
- `publish_many(messages: list[dict]) -> int`:
  - Publica múltiplas mensagens
  - Retorna quantidade publicada
  - Força reconexão em caso de erro
- `close()`: fecha conexão

**Função `_connect() -> pika.BlockingConnection`:**

- Tenta conectar com retry automático
- Delays: [5s, 10s, 30s]
- Na última tentativa, deixa exceção propagar

### app/main.py

Aplicação FastAPI:

- Inicia thread de coleta no lifespan
- Define variáveis globais:
  - `_manual_trigger`: evento para disparo manual
  - `_publisher`: instância de Publisher

- Função `_collect_loop()`:
  - Cria Publisher
  - Loop infinito:
    - Coleta dados
    - Publica tudo
    - Aguarda `COLLECT_INTERVAL` ou trigger manual
    - Limpa flag de trigger

## Como testar

### Verificar saúde

```bash
curl -s http://localhost:8003/health | jq
```

### Forçar coleta manual

```bash
curl -s -X POST http://localhost:8003/coletar-agora | jq
```

### Verificar logs do Docker

```bash
docker compose logs cafeiq-servico-scrapper -f
```

Exemplo de saída:
```
cafeiq-servico-scrapper | 2025-06-16T14:32:10 [INFO] scrapper: Loop de coleta iniciado. Intervalo: 60s
cafeiq-servico-scrapper | 2025-06-16T14:32:12 [INFO] scrapper: Iniciando ciclo de coleta…
cafeiq-servico-scrapper | 2025-06-16T14:32:13 [INFO] scrapper: Ciclo concluído — 4/4 mensagens publicadas.
cafeiq-servico-scrapper | 2025-06-16T14:33:13 [INFO] scrapper: Iniciando ciclo de coleta…
```

## Dados simulados

Todos os dados são simulados (mock). Para usar dados reais:

1. **Notícias**: substituir por API de notícias (exemplo: NewsAPI, BNDES)
2. **Clima**: substituir por API de meteorologia (exemplo: OpenWeatherMap)
3. **Cotação**: substituir por APIs de mercado (exemplo: ICE WebAPI, B3 API)

## Tratamento de erros

- **Conexão com RabbitMQ recusada**: tenta reconectar com delays progressivos
- **Mensagem falha**: registra erro e continua com próximas
- **RabbitMQ inacessível indefinidamente**: publica o máximo que consegue, loga erros

## Notas técnicas

- Usa `pika.BlockingConnection` (conexão síncrona)
- Mensagens são persistentes: se RabbitMQ cair, as mensagens não são perdidas
- Coleta acontece em thread daemon: não bloqueia shutdown do container
- Logging é nível INFO por padrão
- Cada ciclo tem timestamp `coletado_em` UTC ISO format
