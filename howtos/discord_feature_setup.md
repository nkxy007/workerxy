# Discord Bot Setup — How To

A step-by-step guide to creating and configuring a Discord bot ready to communicate with your agent.

---

## Step 1 — Create a Discord Application

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **New Application** (top right)
3. Give it a name (e.g. `NetOpsAgent`) and click **Create**

---

## Step 2 — Create the Bot User

1. In the left sidebar click **Bot**
2. Click **Add Bot** → confirm with **Yes, do it!**
3. Under the bot's username click **Reset Token** → confirm → **copy the token immediately** and save it somewhere safe — you won't see it again
4. Paste it in your `.env` file:
```bash
DISCORD_BOT_TOKEN=your_token_here   # no quotes
```

> **Never share or commit this token.** Anyone with it controls your bot.

---

## Step 3 — Enable Privileged Intents

Still on the **Bot** tab, scroll down to **Privileged Gateway Intents** and enable:

| Intent | Why |
|---|---|
| `MESSAGE CONTENT INTENT` | Required to read what users actually typed |
| `SERVER MEMBERS INTENT` | Optional — needed if you want to look up user details |

Click **Save Changes**.

---

## Step 4 — Generate the Invite URL

1. In the left sidebar click **OAuth2** → **URL Generator**
2. Under **Scopes** check `bot`
3. Under **Bot Permissions** check:
   - `Read Messages / View Channels`
   - `Send Messages`
   - `Read Message History` (optional but useful)
4. Copy the generated URL at the bottom of the page

---

## Step 5 — Create Your Discord Server

If you don't have one yet:

1. Open Discord (browser or app)
2. Click the **+** icon in the left server list
3. Choose **Create My Own** → **For me and my friends**
4. Give it a name and click **Create**

---

## Step 6 — Add the Bot to Your Server

1. Paste the invite URL from Step 4 into your browser
2. Select your server from the dropdown
3. Click **Authorise** and complete the CAPTCHA
4. The bot now appears in your server's member list (shown as offline until your code runs)

---

## Step 7 — Get Your Channel ID

Your agent needs the channel ID to know where to send replies.

1. In Discord open **User Settings** → **Advanced** → enable **Developer Mode**
2. Right-click the channel you want the bot to use
3. Click **Copy Channel ID**
4. Save it — you'll reference this when testing

---

## Step 8 — Restrict the Bot to One Channel (Recommended)

By default the bot can see all channels. To limit it:

1. Go to your server → right-click the channel → **Edit Channel**
2. Click **Permissions** → **+** to add a role or member → select your bot
3. Explicitly **deny** `View Channel` on channels you don't want it reading
4. Explicitly **allow** `View Channel` and `Send Messages` on the one channel it should use

---

## Step 9 — How to Address the Bot

The bot is configured to only respond when directly mentioned. In your Discord channel type:

```
@YourBotName what is the status of router-01
```

The bot will ignore all messages that don't include a mention — this prevents it reacting to every conversation in the channel.

---

## Step 10 — Verify It's Working

Once your bot code is running you should see:

- The bot appears **online** (green dot) in the member list
- Sending `@YourBotName hello` in the channel triggers a response
- If the bot stays offline, your code isn't running or the token is wrong

---

## Quick Reference

| Item | Where to find it |
|---|---|
| Bot token | Developer Portal → your app → Bot → Reset Token |
| Invite URL | Developer Portal → your app → OAuth2 → URL Generator |
| Channel ID | Discord → Developer Mode on → right-click channel → Copy ID |
| Intents setting | Developer Portal → your app → Bot → Privileged Gateway Intents |

---

## Common Errors

| Error | Cause | Fix |
|---|---|---|
| `Improper token has been passed` | Token wrong, truncated, or has quotes | Reset token in portal, re-copy, check `.env` has no quotes |
| Bot is offline after starting code | Wrong token or intents not enabled | Check token, check MESSAGE CONTENT INTENT is on |
| Bot online but not responding | Message doesn't include `@mention` | Always mention the bot by name in your message |
| Bot can't see the channel | Missing channel permissions | Check bot role permissions on that specific channel |

# To Not Miss
For discord feature to work you will need RabbitMQ server running and the RabbitMQ client installed on the machine where you are running the bot.
RabitMQ client listener will be initialized with the following script:
 ```python net_deepagent_cli/communication/discord_bot.py```