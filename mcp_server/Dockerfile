# Build from the project root: docker build -f mcp_server/Dockerfile .
FROM python:3.13-slim
WORKDIR /srv
COPY mcp_server/requirements.txt mcp_server/requirements.txt
RUN pip install --no-cache-dir -r mcp_server/requirements.txt
COPY mcp_server mcp_server
COPY data data
ENV MCP_HOST=0.0.0.0 MCP_PORT=8001
EXPOSE 8001
CMD ["python", "mcp_server/server.py"]