# Como rodar o CaféIQ

---

## Pré-requisitos

### Linux
| Ferramenta | Como instalar |
|---|---|
| Docker Engine + Compose plugin | `curl -fsSL https://get.docker.com | sh` |
| Git | `sudo apt install git` ou `sudo dnf install git` |

Após instalar o Docker, adicione seu usuário ao grupo para não precisar de `sudo`:
```bash
sudo usermod -aG docker $USER
# faça logout e login novamente para o grupo ser aplicado
```

### Windows
| Ferramenta | Como instalar |
|---|---|
| Docker Desktop (inclui Compose) | https://docs.docker.com/desktop/install/windows-install/ |
| Git for Windows | https://git-scm.com/download/win |

> Docker Desktop no Windows exige WSL2 habilitado. O instalador cuida disso automaticamente.
> Use o terminal **PowerShell** ou o **Git Bash** para os comandos abaixo.

---

## Primeira vez (computador novo / clone fresco)

### 1. Clonar o repositório

**Linux / Git Bash (Windows):**
```bash
git clone <url-do-repositorio>
cd cafe-iq
```

**PowerShell (Windows):**
```powershell
git clone <url-do-repositorio>
cd cafe-iq
```

---

### 2. Gerar os lockfiles do Node

Só é necessário se os arquivos `package-lock.json` não estiverem no repositório.
Verifique primeiro:
```bash
ls api-gateway/package-lock.json
ls servico-controlador/package-lock.json
```

Se não existirem, gere-os:

**Linux:**
```bash
cd api-gateway          && npm install && cd ..
cd servico-controlador  && npm install && cd ..
```

**Windows (PowerShell):**
```powershell
cd api-gateway         ; npm install ; cd ..
cd servico-controlador ; npm install ; cd ..
```

---

### 3. Subir os containers

```bash
docker compose up --build
```

O `--build` compila as imagens Docker. Na primeira vez baixa as imagens base (~2 GB total)
e instala as dependências Python e Node — pode levar de 5 a 15 minutos dependendo da conexão.

O sistema está pronto quando você ver estas linhas nos logs:

```
cafeiq-api-gateway           | api-gateway listening on port 3000
cafeiq-servico-rag           | INFO:     Application startup complete.
cafeiq-servico-mcp           | INFO:     Application startup complete.
cafeiq-servico-scrapper      | INFO:     Application startup complete.
cafeiq-servico-controlador   | [INFO] servico-controlador escutando na porta 3001
```

> Deixe este terminal aberto com os logs rodando.
> Para rodar em background (sem travar o terminal): `docker compose up --build -d`

---

### 4. Puxar os modelos do Ollama ⚠️ OBRIGATÓRIO na primeira vez

**Abra um segundo terminal** e execute:

```bash
docker exec cafeiq-ollama ollama pull llama3
docker exec cafeiq-ollama ollama pull nomic-embed-text
```

| Modelo | Tamanho | Uso |
|---|---|---|
| `llama3` | ~4,7 GB | Geração de respostas (LLM) |
| `nomic-embed-text` | ~274 MB | Embeddings para busca vetorial |

Aguarde os dois downloads completarem completamente antes de usar o sistema.

> **Os modelos ficam salvos no volume Docker `ollama-data`.**
> Eles persistem entre reinicializações normais — você **não** precisa baixar novamente
> nas próximas vezes, a menos que apague os volumes com `docker compose down -v`.

---

### 5. Verificar se está tudo funcionando

```bash
curl http://localhost:3000/health
```

Resposta esperada:
```json
{"gateway":"ok","services":[
  {"name":"rag","status":"ok","latencyMs":12},
  {"name":"mcp","status":"ok","latencyMs":5},
  {"name":"controlador","status":"ok","latencyMs":8}
]}
```

---

### 6. Abrir a interface

**Linux:**
```bash
xdg-open index.html
```

**Windows (PowerShell):**
```powershell
Start-Process index.html
```

Ou simplesmente abra o arquivo `index.html` pelo Explorador de Arquivos / Nautilus
(duplo clique → abrir com navegador).

---

## Próximas vezes (mesmo computador)

### Subir o sistema

```bash
docker compose up
```

Sem `--build`. As imagens e os modelos já existem — sobe em menos de 30 segundos.
Os modelos do Ollama **não precisam ser baixados novamente**.

---

### Parar o sistema

```bash
# Se estiver rodando em foreground (logs visíveis):
Ctrl+C

# Se estiver em background (-d):
docker compose stop
```

---

### Quando usar `--build` novamente

Só é necessário quando você **modificar o código** de algum serviço:

```bash
docker compose up --build
```

Para recompilar apenas um serviço específico (mais rápido):
```bash
docker compose up --build servico-rag
```

---

### Resetar tudo do zero

Remove containers **e volumes** (apaga ChromaDB, RabbitMQ e modelos Ollama):

```bash
docker compose down -v
```

Após isso será necessário repetir os **passos 3, 4 e 5** da seção "Primeira vez".

---

## Referência rápida

```
┌─────────────────────────────────────────────────────────────────────┐
│ SITUAÇÃO                          │ COMANDO                         │
├───────────────────────────────────┼─────────────────────────────────┤
│ Clone fresco / PC novo            │ docker compose up --build       │
│                                   │ + pull dos modelos Ollama       │
├───────────────────────────────────┼─────────────────────────────────┤
│ Uso diário (2ª vez em diante)     │ docker compose up               │
├───────────────────────────────────┼─────────────────────────────────┤
│ Após modificar código             │ docker compose up --build       │
├───────────────────────────────────┼─────────────────────────────────┤
│ Parar (preserva dados)            │ Ctrl+C  ou  docker compose stop │
├───────────────────────────────────┼─────────────────────────────────┤
│ Apagar tudo (reset completo)      │ docker compose down -v          │
│                                   │ + pull dos modelos novamente    │
└───────────────────────────────────┴─────────────────────────────────┘
```

---

## Portas dos serviços

| Serviço | URL | Descrição |
|---|---|---|
| Interface web | `index.html` (arquivo local) | Abrir no navegador |
| API Gateway | http://localhost:3000 | Ponto de entrada da API |
| RabbitMQ (painel) | http://localhost:15672 | Usuário: `cafeiq` / Senha: `cafeiq123` |
| ChromaDB | http://localhost:8000 | Banco vetorial |
| Ollama | http://localhost:11434 | Servidor LLM |
