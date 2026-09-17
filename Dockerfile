FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 FU_WORKSPACE=/workspace OLLAMA_HOST=http://host.docker.internal:11434
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /workspace/logs /workspace/sessions /workspace/generated
ENTRYPOINT ["python", "agent.py"]
CMD ["selftest"]
