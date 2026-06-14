# rss-proxy-vps

Self-hosted RSS proxy for `blog.mornati.net`, served from the `pygame.ovh` VPS via Coolify.

This replaces the previous Cloudflare Worker (`rss-proxy/`) that GitHub Actions could no longer reach.

## Architecture

```
GitHub Action (blog-post-workflow.yml)
  -> GET https://rss.pygame.ovh/rss.xml
       -> Coolify's built-in Traefik (auto TLS)
            -> this container (Node.js + Express)
                 -> upstream: https://blog.mornati.net/rss.xml
                 -> in-memory cache (default TTL: 1h)
                 -> endpoints: /rss.xml, /health, POST /refresh
```

The connection from GitHub Actions reaches the VPS directly (no Cloudflare in the path), so it is not subject to Cloudflare WAF rules that block GitHub Actions IPs.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/rss.xml` | Cached RSS feed. Returns `X-Cache: HIT|MISS|STALE->FRESH|STALE`. |
| GET | `/health` | JSON health probe (200 if last fetch < 2× TTL, 503 otherwise). |
| POST | `/refresh` | Invalidate the cache. Requires `X-Refresh-Token: <REFRESH_SECRET>`. |
| GET | `/` | Tiny status page. |

## Environment variables

| Name | Default | Notes |
|---|---|---|
| `RSS_URL` | `https://blog.mornati.net/rss.xml` | Upstream RSS feed URL. |
| `CACHE_TTL_SECONDS` | `3600` | Cache lifetime in seconds. |
| `PORT` | `3000` | HTTP port. |
| `NODE_ENV` | `production` | Standard. |
| `REFRESH_SECRET` | _(empty = endpoint disabled)_ | Shared secret for `POST /refresh`. |

Generate a secret:
```bash
openssl rand -hex 32
```

## Local development

```bash
cd rss-proxy-vps
npm install
RSS_URL=https://blog.mornati.net/rss.xml \
REFRESH_SECRET=dev \
npm start
# in another shell:
curl -i http://localhost:3000/health
curl -i http://localhost:3000/rss.xml
curl -X POST -H "X-Refresh-Token: dev" http://localhost:3000/refresh
```

## Deploy via Coolify

1. **DNS** — in the OVH zone for `pygame.ovh`, add an A record:
   - `rss` → `<VPS public IPv4>`, TTL 300

2. **Coolify** — create a new Application:
   - Source: `https://github.com/mmornati/mmornati`, branch `main`
   - Build Pack: **Dockerfile**
   - Base Directory: `rss-proxy-vps`     ← this is the docker build context
   - Dockerfile Location: `Dockerfile`    ← path is RELATIVE to the Base Directory above
   - Port: `3000`
   - FQDN: `https://rss.pygame.ovh` (proxy enabled — default)
   - Env vars: see table above, and **uncheck "Available at Buildtime"** for every variable (they are only read at runtime by `server.js`). This avoids Coolify's warning about `NODE_ENV=production` skipping devDependencies.

3. **Deploy** and verify:
   ```bash
   curl -i https://rss.pygame.ovh/health
   curl -i https://rss.pygame.ovh/rss.xml
   ```

4. **Update the GitHub Action** in `.github/workflows/blog-post-workflow.yml`:
   ```yaml
   feed_list: "https://rss.pygame.ovh/rss.xml"
   ```

5. **Cleanup** — delete the legacy Cloudflare Worker (`rss-proxy` in the Cloudflare dashboard) and remove the `rss-proxy/` directory from this repo.

## Docker image

Built from `Dockerfile` in this directory. Multi-step:

1. `node:20-alpine` base
2. `npm ci --omit=dev` for dependencies
3. Runs as non-root `node` user
4. Exposes port `3000`

## Notes

- The cache is in-memory only — restarting the container drops it (next request refetches).
- Stale-on-error: if the upstream is unreachable but a previous value exists in cache, the service returns the stale value with `X-Cache: STALE` instead of failing.
- The service is stateless aside from the in-memory cache. No volumes or external services required.
