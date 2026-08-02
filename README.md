# Apprenticeship application checker

Checks a list of pages every day and messages you on Telegram when applications open.
Runs in the cloud via GitHub Actions, so your own computer doesn't need to be on.

## Files
```
check.py                       # the checker
targets.json                   # the pages you're watching (edit this)
.github/workflows/check.yml    # the daily schedule
state.json                     # auto-generated, don't touch
```

## Setup (one-off, ~15 min)

1. **Make a repo.** Create a new GitHub repository and put these files in it,
   keeping the `.github/workflows/` folder structure exactly as-is.

2. **Make a Telegram bot.**
   - Message `@BotFather` on Telegram, send `/newbot`, follow the prompts.
   - Copy the **token** it gives you.
   - Send any message to your new bot (once), then open:
     `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   - Find `"chat":{"id": ...}` in the response - that number is your **chat id**.

3. **Add the secrets.** In the repo: Settings -> Secrets and variables -> Actions
   -> New repository secret. Add two:
   - `TELEGRAM_TOKEN`
   - `TELEGRAM_CHAT_ID`

4. **Fill in targets.json.** Replace the examples with real scheme pages. Per target:
   - `open_keywords`  - text that appears when it's open ("apply now", etc.)
   - `closed_keywords` - text shown while closed ("opening soon"); prevents false alarms
   - `selector` - optional CSS selector to check just one part of the page (or `null`)
   - `watch_changes` - `true` to also alert on *any* change to the page (noisier)

5. **Test it.** Actions tab -> apprenticeship-checker -> Run workflow. Check the log
   and your Telegram. The first run sets a baseline and reports current status.

## Known limitation: JavaScript pages
Many career sites load their listings with JavaScript. A plain fetch sees an empty
shell, so a live scheme may read as "closed" forever. If that happens, that page needs
a headless-browser version (Playwright) instead - ask and it's a quick swap.
