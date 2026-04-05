FROM python:3.13-slim

# System deps: gcc for psycopg, libpq for postgres, supervisor to run both services
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project structure
COPY alembic.ini .
COPY alembic/ ./alembic/
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY templates/ ./templates/

# Supervisor and startup
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY start.sh /start.sh
RUN chmod +x /start.sh

# FastAPI on 8000, Streamlit on 8080
EXPOSE 8000 8080

CMD ["/start.sh"]