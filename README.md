# Crypto Telegram Bot

A feature-rich Telegram bot built with Python for checking real-time cryptocurrency prices, managing periodic price update subscriptions, and setting custom price alerts. This project is containerized with Docker for easy deployment.


## ✨ Features

-   **Live Price Check:** Get the latest price of any cryptocurrency by its name (English or Persian) or symbol.
-   **Price Subscriptions:** Subscribe to receive automatic price updates for your favorite currencies daily, weekly, or monthly.
-   **Custom Price Alerts:** Set an alert to be notified when a currency's price goes **above** or **below** a specific target.
-   **Interactive Menus:** Easy-to-use interface with inline keyboard buttons.
-   **Persistent State:** The bot remembers your conversations and settings even after a restart.

## 🛠️ Tech Stack

-   **Language:** Python 3.12
-   **Bot Framework:** `python-telegram-bot`
-   **Database:** MongoDB (using the `pymongo` async driver)
-   **Background Jobs:** `APScheduler`
-   **Containerization:** Docker & Docker Compose

## 🚀 How to Run

This application is containerized and available on Docker Hub. The easiest way to run it is using Docker.

### Prerequisites

-   Docker and Docker Compose installed.
-   A Telegram Bot Token from BotFather.
-   A running MongoDB instance.
-   An API key from a provider like Wallex.

### Running with Docker

1.  Create a `.env` file in your directory with the following content:

    ```env
    TELEGRAM_TOKEN="YOUR_TELEGRAM_TOKEN"
    MONGO_URI="mongodb://your_mongo_user:your_mongo_password@your_mongo_host:27017/"
    DB_NAME="crypto_bot_db"
    API_KEY="YOUR_API_KEY"
    ```

2.  Pull the image from Docker Hub and run it using the `.env` file:

    ```bash
    docker run -d --name crypto-bot --env-file ./.env rezagp/crypto-telegram-bot:latest
    ```

### (Recommended) Running with Docker Compose

For an easier setup that includes a MongoDB service, you can use the provided `docker-compose.yml` file.

1.  Create the `.env` file as described above.
2.  Run the following command in your terminal:

    ```bash
    docker-compose up -d
    ```
This will start both the bot and a dedicated MongoDB container.
