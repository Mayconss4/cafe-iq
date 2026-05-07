const express = require('express');
const axios = require('axios');

const app = express();
const PORT = process.env.PORT || 3000;

const SERVICES = {
  rag: process.env.RAG_URL || 'http://servico-rag:8001',
  mcp: process.env.MCP_URL || 'http://servico-mcp:8002',
  controlador: process.env.CONTROLADOR_URL || 'http://servico-controlador:3001',
};

// Fix 1: CORS — permite requisições do browser (incluindo file://)
app.use((req, res, next) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.sendStatus(204);
  next();
});

app.use(express.json());

app.use((req, _res, next) => {
  req._startTime = Date.now();
  next();
});

app.use((req, res, next) => {
  const original = res.end.bind(res);
  res.end = (...args) => {
    const ms = Date.now() - req._startTime;
    console.log(`${req.method} ${req.path} ${res.statusCode} ${ms}ms`);
    return original(...args);
  };
  next();
});

app.post('/chat', async (req, res) => {
  try {
    const { data, status } = await axios.post(`${SERVICES.rag}/query`, req.body);
    res.status(status).json(data);
  } catch (err) {
    forwardError(res, err);
  }
});

app.post('/mcp/tool', async (req, res) => {
  try {
    const { data, status } = await axios.post(`${SERVICES.mcp}/invoke`, req.body);
    res.status(status).json(data);
  } catch (err) {
    forwardError(res, err);
  }
});

app.get('/health', async (_req, res) => {
  // Fix 2: captura entries antes do allSettled para preservar o nome no caso de falha
  const entries = Object.entries(SERVICES);
  const checks = await Promise.allSettled(
    entries.map(async ([name, url]) => {
      const start = Date.now();
      await axios.get(`${url}/health`, { timeout: 3000 });
      return { name, status: 'ok', latencyMs: Date.now() - start };
    })
  );

  const results = checks.map((r, i) =>
    r.status === 'fulfilled'
      ? r.value
      : { name: entries[i][0], status: 'unreachable', error: r.reason.message }
  );

  const allOk = results.every((r) => r.status === 'ok');
  res.status(allOk ? 200 : 207).json({ gateway: 'ok', services: results });
});

function forwardError(res, err) {
  if (err.response) {
    res.status(err.response.status).json(err.response.data);
  } else {
    res.status(502).json({ error: 'Bad Gateway', detail: err.message });
  }
}

app.listen(PORT, () => {
  console.log(`api-gateway listening on port ${PORT}`);
});
