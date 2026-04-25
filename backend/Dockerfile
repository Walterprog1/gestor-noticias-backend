FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port (Railway will override with PORT env, but relies on EXPOSE)
EXPOSE 8000

# Run the application
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port 8000"