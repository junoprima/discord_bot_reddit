
# Discord Reddit Bot

A Discord bot that fetches posts from specific subreddits and sends them to Discord channels using webhooks. This project is containerized with Docker for seamless deployment and scalability.

---

## Features
- Fetches and sends posts from specific subreddits to Discord channels.
- Dynamically subscribes/unsubscribes to subreddits.
- Configurable through environment variables.
- Runs efficiently using Docker.
- Includes enhanced logging for better debugging and monitoring.

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Setup Instructions](#setup-instructions)
3. [Environment Variables](#environment-variables)
4. [Docker Usage](#docker-usage)
5. [Deployment](#deployment)
6. [Logging and Monitoring](#logging-and-monitoring)
7. [Contributing](#contributing)
8. [License](#license)

---

## Prerequisites

Ensure you have the following installed:
1. Python 3.9+ (if running locally)
2. Docker and Docker Compose
3. Firebase credentials for Firestore integration
4. Reddit API credentials
5. Discord bot token

---

## Setup Instructions

1. **Clone the Repository**
   ```bash
   git clone https://github.com/your_username/discord_bot_reddit.git
   cd discord_bot_reddit
   ```

2. **Prepare Environment Variables**
   Create a `.env` file in the project root with the following variables:
   ```plaintext
   DISCORD_TOKEN=your_discord_token
   FIREBASE_CREDENTIALS=/app/firebase_key.json
   REDDIT_CLIENT_ID=your_reddit_client_id
   REDDIT_CLIENT_SECRET=your_reddit_client_secret
   REDDIT_USER_AGENT=your_reddit_user_agent
   ```

3. **Add Firebase Credentials**
   Place the `firebase_key.json` file in the root directory.

4. **Run the Bot with Docker**
   Build and run the container:
   ```bash
   docker compose up -d
   ```

5. **Stopping the Bot**
   To stop the bot, use:
   ```bash
   docker compose down
   ```

---

## Environment Variables

| Variable               | Description                                     |
|------------------------|-------------------------------------------------|
| `DISCORD_TOKEN`        | Your Discord bot token.                        |
| `FIREBASE_CREDENTIALS` | Path to Firebase JSON credentials.             |
| `REDDIT_CLIENT_ID`     | Reddit API Client ID.                          |
| `REDDIT_CLIENT_SECRET` | Reddit API Client Secret.                      |
| `REDDIT_USER_AGENT`    | User agent for Reddit API requests.            |

---

## Docker Usage

1. **Build the Docker Image**
   ```bash
   docker compose build
   ```

2. **Run the Docker Container**
   ```bash
   docker compose up -d
   ```

3. **Rebuild After Code Changes**
   ```bash
   docker compose down
   docker compose build
   docker compose up -d
   ```

4. **Monitor Docker Logs**
   ```bash
   docker logs reddit_feed_bot
   ```

---

## Deployment

### Using DigitalOcean
1. **Create a Droplet**
   - Use Ubuntu 22.04 LTS as the base image.
   - Install Docker and Docker Compose.

2. **Set Up SSH Access**
   - Generate an SSH key using `ssh-keygen`.
   - Add the public key to your DigitalOcean project.

3. **Clone the Repository**
   ```bash
   git clone https://github.com/your_username/discord_bot_reddit.git
   cd discord_bot_reddit
   ```

4. **Run Docker**
   ```bash
   docker compose up -d
   ```

---

## Logging and Monitoring

1. Logs are stored in the `logs` directory.
2. Use the following commands to view logs:
   - Docker logs:
     ```bash
     docker logs reddit_feed_bot
     ```
   - Application logs:
     ```bash
     tail -f logs/reddit_feed_bot.log
     ```

---

## Contributing

We welcome contributions! Please follow these steps:
1. Fork the repository.
2. Create a new branch: `git checkout -b feature-name`.
3. Commit your changes: `git commit -m "Add feature"`.
4. Push to your branch: `git push origin feature-name`.
5. Submit a pull request.

---

## License

This project is licensed under the MIT License. See the LICENSE file for details.
