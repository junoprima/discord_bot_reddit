# Use Python as the base image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy application files
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Supervisor
RUN apt-get update && apt-get install -y supervisor && apt-get clean

# Copy Supervisor configuration file
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Expose port (optional)
EXPOSE 5000

# Start Supervisor
CMD ["/usr/bin/supervisord"]
