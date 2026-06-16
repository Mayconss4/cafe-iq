# Serviço Scrapper - Diagramas de Classe

## Visão geral

O `servico-scrapper` é responsável por coletar dados periódicos e publicar mensagens no RabbitMQ.

## Componentes principais

- `main.py`
  - `_collect_loop()`
  - `lifespan()`
  - `GET /health`
  - `POST /coletar-agora`
- `collectors.py`
  - `run_cycle()`
  - `collect_noticias()`
  - `collect_clima()`
  - `collect_cotacao()`
  - fetchers e parsers de sites externos
- `publisher.py`
  - `Publisher`
  - `_ensure_connected()`
  - `publish()`
  - `publish_many()`
- `config.py`
  - variáveis de ambiente

## Diagrama de classes

```mermaid
classDiagram
    class ScrapperApp {
        +app
        +lifespan(_app)
        +GET /health()
        +POST /coletar-agora()
    }
    class Collectors {
        +run_cycle(): list[dict]
        +collect_noticias(): list[dict]
        +collect_clima(): dict
        +collect_cotacao(): dict
    }
    class Publisher {
        -_conn
        -_channel
        +publish(message)
        +publish_many(messages)
        +close()
    }
    class Config {
        +RABBITMQ_HOST
        +RABBITMQ_PORT
        +RABBITMQ_USER
        +RABBITMQ_PASS
        +QUEUE_NAME
        +COLLECT_INTERVAL
    }
    class HttpFetcher {
        +_fetch_html(url)
    }

    ScrapperApp --> Collectors : usa
    ScrapperApp --> Publisher : usa
    Publisher --> Config : usa
    Collectors --> HttpFetcher : usa
```

## Descrição dos relacionamentos

- `ScrapperApp` inicia o loop de coleta e expõe endpoints de saúde e disparo manual.
- `Collectors` produz a lista de mensagens para publicação e implementa parse de sites externos.
- `Publisher` gerencia conexão RabbitMQ e publica mensagens.
- `Config` concentra as variáveis de ambiente utilizadas pelo serviço.
