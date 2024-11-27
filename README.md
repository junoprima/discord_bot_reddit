
# Discord Reddit Bot

A Discord bot that fetches posts from specific subreddits and sends them to a Discord channel. This project is set up to run using Docker and can be deployed on DigitalOcean.

## Features
- Fetches posts from specific subreddits.
- Sends posts to Discord channels using webhooks.
- Configurable via `.env` file.
- Deployable with Docker for seamless containerization.
- Includes logging for better debugging and monitoring.

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Setup Instructions](#setup-instructions)
3. [Environment Variables](#environment-variables)
4. [Docker Usage](#docker-usage)
5. [Deployment on DigitalOcean](#deployment-on-digitalocean)
6. [Logs and Monitoring](#logs-and-monitoring)
7. [Contributing](#contributing)
8. [License](#license)

---

## Prerequisites
Ensure you have the following installed:
1. Python 3.10+
2. Docker and Docker Compose
3. A DigitalOcean account (optional, for deployment)
4. Git

---

## Setup Instructions

1. **Clone the Repository**
   ```bash
   git clone https://github.com/your_username/discord_bot_reddit.git
   cd discord_bot_reddit
   ```

2. **Install Python Dependencies**
   (Only needed if running outside Docker)
   ```bash
   pip install -r requirements.txt
   ```

3. **Add the `.env` File**
   Create a `.env` file in the project root:
   ```plaintext
   DISCORD_TOKEN=your_discord_token
   CHANNEL_ID=your_channel_id
   FIREBASE_CREDENTIALS=/path/to/firebase_key.json
   REDDIT_CLIENT_ID=your_reddit_client_id
   REDDIT_CLIENT_SECRET=your_reddit_client_secret
   REDDIT_USER_AGENT=your_reddit_user_agent
   ```

4. **Add the `firebase_key.json` File**
   Place the Firebase credentials file in the root directory.

---

## Environment Variables

Ensure the following variables are set in the `.env` file:

| Variable              | Description                                     |
|-----------------------|-------------------------------------------------|
| `DISCORD_TOKEN`       | Your Discord bot token.                        |
| `CHANNEL_ID`          | The ID of the Discord channel.                 |
| `FIREBASE_CREDENTIALS`| Path to your Firebase JSON credentials.        |
| `REDDIT_CLIENT_ID`    | Reddit API Client ID.                          |
| `REDDIT_CLIENT_SECRET`| Reddit API Client Secret.                      |
| `REDDIT_USER_AGENT`   | User agent for Reddit API requests.            |

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

3. **Stop the Docker Container**
   ```bash
   docker compose down
   ```

4. **Rebuild After Code Changes**
   ```bash
   docker compose down
   docker compose build
   docker compose up -d
   ```

---

## Deployment on DigitalOcean

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

4. **Run Docker on DigitalOcean**
   ```bash
   docker compose up -d
   ```

5. **Monitor the Logs**
   ```bash
   docker logs <container_name>
   ```

---

## Logs and Monitoring

1. Logs are stored in the `logs` directory inside the project.
2. Use the following commands to check logs:
   - Docker logs:
     ```bash
     docker logs <container_name>
     ```
   - Application logs:
     ```bash
     tail -f logs/app.log
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

---
