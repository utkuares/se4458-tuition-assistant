# Kong + API in one image (Azure express only allows one container per app).
# Build from the project root after rendering gateway/kong.azure.yml
FROM kong:3.9
USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/venv
COPY api/requirements.txt /srv/api/requirements.txt
RUN /opt/venv/bin/pip install --no-cache-dir -r /srv/api/requirements.txt
COPY api /srv/api
COPY gateway/kong.azure.yml /kong/kong.yml
COPY gateway/start.sh /start.sh
RUN chmod +x /start.sh
ENV KONG_DATABASE=off \
    KONG_DECLARATIVE_CONFIG=/kong/kong.yml \
    KONG_PROXY_LISTEN=0.0.0.0:8080 \
    KONG_ADMIN_LISTEN=off \
    KONG_PROXY_ACCESS_LOG=/dev/stdout \
    KONG_PROXY_ERROR_LOG=/dev/stderr \
    KONG_TRUSTED_IPS=0.0.0.0/0,::/0 \
    KONG_REAL_IP_HEADER=X-Forwarded-For
USER kong
EXPOSE 8080
ENTRYPOINT ["/start.sh"]
