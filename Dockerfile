FROM python:3.9-slim

WORKDIR /app

COPY file_server.py .
COPY client.py .

RUN mkdir -p /app/content

EXPOSE 8080

CMD ["python", "file_server.py", "/app/content"]
