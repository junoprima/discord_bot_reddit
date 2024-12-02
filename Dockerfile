# Use Python as the base image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy application files
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port (optional)
EXPOSE 5000

# Start the bot
CMD ["python", "bot.py"]  # Updated to new consolidated file
