FROM python:3.11-slim

WORKDIR /app

# Copy project files
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
# Run the AI application
CMD ["python", "main.py"]
