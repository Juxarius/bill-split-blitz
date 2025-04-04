# Use Python 3.12 as the base image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies (git)
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Clone the repository
RUN git clone https://github.com/Juxarius/bill-split-blitz.git repo

# Copy the config file from your local context to the container
COPY blitz/config.json /app/repo/blitz/config.json
COPY certs /app/repo/certs

# Change working directory to the cloned repo
WORKDIR /app/repo

# Install Python dependencies if needed
RUN pip install -r requirements.txt

# Expose port 80 to the outside world
EXPOSE 80

# Run the main.py script
CMD ["python", "blitz/main.py"]
