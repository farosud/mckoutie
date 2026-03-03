FROM python:3.12-slim

WORKDIR /app

# Install system deps for weasyprint
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 \
    libffi-dev libcairo2 && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps (layer cached separately from source code)
COPY pyproject.toml .
RUN pip install --no-cache-dir pip setuptools wheel && \
    pip install --no-cache-dir $(python -c "
import tomllib
with open('pyproject.toml', 'rb') as f:
    data = tomllib.load(f)
deps = data.get('project', {}).get('dependencies', [])
print(' '.join(deps))
")

# Copy source code
COPY . .

# Create reports dir
RUN mkdir -p reports

EXPOSE 8000

CMD ["python", "main.py"]
