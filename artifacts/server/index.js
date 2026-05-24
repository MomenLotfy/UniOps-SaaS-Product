'use strict';
const express = require('express');
const app = express();
const PORT = process.env.PORT || 3001;

app.use(express.json());

app.get('/health', (_req, res) => {
  res.json({ status: 'ok', service: 'node_api', version: '1.0.0' });
});

app.get('/api/status', (_req, res) => {
  res.json({ status: 'running', timestamp: new Date().toISOString() });
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`UniOps Node API listening on port ${PORT}`);
});
