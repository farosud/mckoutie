FROM python:3.12-slim

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Create reports dir
RUN mkdir -p reports

EXPOSE 8000

CMD ["python", "main.py"]
