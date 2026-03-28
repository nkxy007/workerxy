# Notification Webhook Setup Guide

This guide explains how to set up Discord and Slack integrations for the WorkerXY Agent.

## 1. Slack Setup (Full Bot via Socket Mode & Webhooks)

WorkerXY supports two types of Slack integrations: a full two-way chat bot, and simple permission request webhooks.

### A. Full Chat Bot Setup (Socket Mode)
To let users chat with WorkerXY from Slack without exposing a public webhook URL, we use Socket Mode.

1.  **Create an App**: Go to [api.slack.com/apps](https://api.slack.com/apps) and click **"Create New App"** (choose "From scratch").
2.  **Name the App**: Name your app (e.g., "WorkerXY Bot") and select your workspace.
3.  **Enable Socket Mode**: Go to **Settings → Socket Mode**.
    *   ✅ Toggle **Enable Socket Mode** to On.
    *   ✅ Generate an **App-Level Token** (it must start with `xapp-`).
    *   ✅ Grant it the `connections:write` scope.
4.  **Configure Bot Permissions**: Go to **Features → OAuth & Permissions**.
    *   Under **Bot Token Scopes**, add: `app_mentions:read`, `chat:write`, `channels:history`, `im:history`.
5.  **Enable Events**: Go to **Features → Event Subscriptions**.
    *   Toggle **Enable Events** to On.
    *   Under **Subscribe to bot events**, add `app_mention` and `message.im`.
6.  **Install App**: Go to **Install App** and click **Install to Workspace**.
    *   Copy the **Bot User OAuth Token** (starts with `xoxb-`).
7.  **Credentials**: Add these to your `creds.py` or `.env` file:
    ```python
    SLACK_BOT_AUTH_TOKEN = "xoxb-YOUR-BOT-TOKEN"
    SLACK_BOT_SOCKET_TOKEN = "xapp-YOUR-APP-LEVEL-TOKEN"
    ```
    *You can now trigger the bot by running `workerxy slack` in your terminal!*

### B. Simple Permission Webhooks
If you only want permission request notifications sent to a channel (no two-way chat):

1. Go to the **"Incoming Webhooks"** section of your app and toggle it **On**.
2. Click **"Add New Webhook to Workspace"** and select a channel.
3. Use the copied URL for your `creds.py` or `.env`:
   ```python
   SLACK_PERMISSION_WEBHOOK = "YOUR_WEBHOOK_URL"
   ```

### How to Test the Slack Webhook:
You can use `curl` in your terminal to test the webhook:
```bash
curl -X POST -H 'Content-type: application/json' --data '{"text":"Hello, world!"}' YOUR_WEBHOOK_URL
```

---

## 2. Discord Setup (Webhooks)

Discord webhooks are a simple way to post messages to a specific channel without needing a full bot user.

### Steps to Add a Webhook in Discord:

1.  **Open Server Settings**: Navigate to your Discord server and click the server name (top left) then **Server Settings**.
2.  **Go to Integrations**: Click on the **Integrations** tab in the left sidebar.
3.  **Create Webhook**: Click **Webhooks**, then click **New Webhook**.
4.  **Configure Webhook**:
    *   Set a **Name** (e.g., "WorkerXY Permissions").
    *   Select the **Channel** where notifications should appear.
5.  **Copy URL**: Click **Copy Webhook URL**.

### How to Test the Discord Webhook:
You can use `curl` to test the Discord webhook:
```bash
curl -X POST -H "Content-Type: application/json" -d '{"content": "Hello, Discord!"}' YOUR_WEBHOOK_URL
```

---

## 3. Configuration in WorkerXY

Once you have your webhook URLs, you can configure them in one of two ways:

### Using Environment Variables
Set the following environment variables in your `.env` file or shell:
*   `DISCORD_PERMISSION_WEBHOOK`: Your Discord Webhook URL.
*   `SLACK_PERMISSION_WEBHOOK`: Your Slack Webhook URL.

### Using `creds.py`
Add the following to your `creds.py` file:
```python
DISCORD_PERMISSION_WEBHOOK = "YOUR_DISCORD_WEBHOOK_URL"
SLACK_PERMISSION_WEBHOOK = "YOUR_SLACK_WEBHOOK_URL"
```
