# Use a Playwright-ready image from Microsoft
FROM mcr.microsoft.com/playwright/python:v1.41.2-focal

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install Tesseract and other system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libgl1 \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Set PYTHONPATH to include backend
ENV PYTHONPATH=/app

# Expose the port
EXPOSE 8002

# Run the application
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8002"]
