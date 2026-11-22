# Hybrid deployment: API/MCP run in host Conda agent-dev; this builds Redis only.
FROM redis:7-alpine@sha256:7f7d30b7fdd09467bac58198a1f166dd69789d348d4fe859cccb20e0cf287fbe
COPY deploy/redis/redis.conf /usr/local/etc/redis/redis.conf
USER redis
HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=12 CMD ["redis-cli", "ping"]
CMD ["redis-server", "/usr/local/etc/redis/redis.conf"]
