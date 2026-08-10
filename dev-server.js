#!/usr/bin/env node
/* ============================================================
 * dev-server.js — zero-dependency local server
 *
 *   node dev-server.js          -> http://localhost:4173
 *   node dev-server.js 5000     -> custom port
 *
 * Serves the deck as static files and accepts POST /save from
 * the inline editor, writing content/slides.json in place.
 * Not needed in production: Netlify serves the same files, and
 * the editor falls back to downloading the JSON there.
 * ============================================================ */

const http = require('http');
const fs = require('fs');
const path = require('path');

const ROOT = __dirname;
const PORT = Number(process.argv[2]) || 4173;
const CONTENT_FILE = path.join(ROOT, 'content', 'slides.json');

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.csv': 'text/csv; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
};

const server = http.createServer((req, res) => {
  // --- save endpoint -------------------------------------------------
  if (req.method === 'POST' && req.url === '/save') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      try {
        JSON.parse(body); // refuse to write invalid JSON
        // Keep one rolling backup, just in case.
        if (fs.existsSync(CONTENT_FILE)) {
          fs.copyFileSync(CONTENT_FILE, CONTENT_FILE + '.bak');
        }
        fs.writeFileSync(CONTENT_FILE, body);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end('{"ok":true}');
        console.log(`[saved] content/slides.json  ${new Date().toLocaleTimeString()}`);
      } catch (e) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: false, error: String(e.message) }));
        console.error('[save rejected]', e.message);
      }
    });
    return;
  }

  // --- static files --------------------------------------------------
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    res.writeHead(405).end();
    return;
  }

  let urlPath = decodeURIComponent(req.url.split('?')[0]);
  if (urlPath === '/') urlPath = '/index.html';

  const filePath = path.join(ROOT, urlPath);
  // Prevent escaping the project directory.
  if (!filePath.startsWith(ROOT + path.sep) && filePath !== ROOT) {
    res.writeHead(403).end('Forbidden');
    return;
  }

  fs.readFile(filePath, (err, data) => {
    if (err) {
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end(`Not found: ${urlPath}`);
      return;
    }
    const ext = path.extname(filePath).toLowerCase();
    res.writeHead(200, {
      'Content-Type': MIME[ext] || 'application/octet-stream',
      'Cache-Control': 'no-store',
    });
    res.end(data);
  });
});

server.listen(PORT, () => {
  console.log('');
  console.log('  Deck dev server running:');
  console.log(`    view   http://localhost:${PORT}`);
  console.log(`    edit   http://localhost:${PORT}/?edit`);
  console.log('');
  console.log('  Edits made in the browser save directly to content/slides.json');
  console.log('  (a rolling backup is kept at content/slides.json.bak)');
  console.log('');
});
