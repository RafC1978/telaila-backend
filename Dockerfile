# Use the official Python image
FROM python:3.11-slim

# Ensure logs are sent straight to the terminal
ENV PYTHONUNBUFFERED True

# Set the working directory in the container
WORKDIR /app

# Copy all files from your GitHub repo into the container
COPY . .

# Install the dependencies from your requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Google Cloud Run uses the PORT environment variable
ENV PORT=8080

# Start the application. 
# Based on your file list, it looks like 'webhook_server.py' is your main entry point.
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 webhook_server:app
