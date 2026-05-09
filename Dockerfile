FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    strands-agents \
    strands-agents-tools \
    strands-agents-bedrock \
    fastapi \
    uvicorn[standard] \
    aiofiles

COPY backend/app/server.py ./server.py
COPY frontend/index.html ./frontend/index.html

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
