FROM python:3.13-slim

# System packages needed for Pillow (fastapi-storages uses ImageType)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    libwebp-dev \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy entire repo so src/hyperadmin is available
COPY . .

# Install hyperadmin from source, aiosqlite (async SQLite driver), then rbac_app deps
RUN pip install --no-cache-dir -e /app aiosqlite && \
    pip install --no-cache-dir -r /app/examples/rbac_app/requirements.txt

# Directories for uploaded files and persistent DB
RUN mkdir -p /app/uploads/avatars /app/uploads/user_pk /app/data

EXPOSE 8000

CMD ["uvicorn", "examples.rbac_app.main:app", "--host", "0.0.0.0", "--port", "8000"]
