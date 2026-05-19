const express = require('express');
const axios = require('axios');

const app = express();
const PORT = process.env.PORT || 3001;

const GATEWAY_URL = process.env.GATEWAY_URL || 'http://api-gateway:3000';
const SCRAPPER_URL = process.env.SCRAPPER_URL || 'http://servico-scrapper:8003';

// ---------------------------------------------------------------------------
// In-memory log ring buffer (max 20 entries)
// ---------------------------------------------------------------------------
const MAX_LOGS = 20;
const _logs = [];

function addLog(level, message, meta = {}) {
  const entry = { timestamp: new Date().toISOString(), level, message, ...meta };
  _logs.push(entry);
  if (_logs.length > MAX_LOGS) _logs.shift();
  console.log(`[${entry.level.toUpperCase()}] ${entry.message}`);
}

// ---------------------------------------------------------------------------
// Middleware
// ---------------------------------------------------------------------------
app.use(express.json());

app.use((req, _res, next) => {
  req._startTime = Date.now();
  next();
});

app.use((req, res, next) => {
  const original = res.end.bind(res);
  res.end = (...args) => {
    addLog('info', `${req.method} ${req.path} → ${res.statusCode}`, {
      ms: Date.now() - req._startTime,
    });
    return original(...args);
  };
  next();
});

// ---------------------------------------------------------------------------
// Routes
// ---------------------------------------------------------------------------
app.get('/health', (_req, res) => {
  res.json({ status: 'ok' });
});

app.get('/status', async (_req, res) => {
  try {
    const { data, status } = await axios.get(`${GATEWAY_URL}/health`, { timeout: 5000 });
    res.status(status).json({ origem: 'api-gateway', ...data });
  } catch (err) {
    const detail = err.response?.data ?? err.message;
    addLog('error', `GET /status falhou: ${err.message}`);
    res.status(502).json({ error: 'Não foi possível contatar o api-gateway.', detail });
  }
});

app.post('/forcar-ingestao', async (_req, res) => {
  try {
    const { data, status } = await axios.post(
      `${SCRAPPER_URL}/coletar-agora`,
      {},
      { timeout: 5000 },
    );
    res.status(status).json(data);
  } catch (err) {
    const detail = err.response?.data ?? err.message;
    addLog('error', `POST /forcar-ingestao falhou: ${err.message}`);
    res.status(502).json({ error: 'Não foi possível contatar o servico-scrapper.', detail });
  }
});

app.get('/logs', (_req, res) => {
  res.json({ total: _logs.length, logs: [..._logs].reverse() });
});

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
app.listen(PORT, () => {
  addLog('info', `servico-controlador escutando na porta ${PORT}`);
});
