#!/bin/bash
set -e

# Start a lightweight Python health check server (Does NOT serve files)
# This is required because Cloud Run needs the container to listen on $PORT
echo "Starting dummy health check server on port $PORT..."
python -c '
import os, socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(("", int(os.environ["PORT"])))
s.listen(1)
while True:
    conn, _ = s.accept()
    conn.recv(1024)
    conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK")
    conn.close()
' &

# Start the Celery worker
echo "Starting Celery worker..."
celery -A config worker --loglevel=info --concurrency=2
