# Anjani Bot

A feature-rich Telegram group management bot built with [Pyrogram](https://github.com/pyrogram/pyrogram) and MongoDB.

---

## Requirements

- Python 3.10+
- MongoDB instance
- Telegram API credentials (`API_ID`, `API_HASH`)
- Bot token from [@BotFather](https://t.me/botfather)

## Setup

1. Copy `.env.example` to `config.env` and fill in the values.
2. Install dependencies:
   ```bash
   pip install poetry
   poetry install
   ```
3. Run the bot:
   ```bash
   python -m anjani
   ```

---

## Available Commands

### General

| Command | Description |
|---------|-------------|
| `/start` | Start the bot / show welcome message |
| `/help` | Show help menu with all plugins |
| `/ping` | Check bot response latency |
| `/id` | Get chat, message, user, or file ID |
| `/paste [service]` | Paste replied text/document to a paste service (`stashbin`, `hastebin`, `spacebin`) |
| `/slap` | Slap a user with a neko GIF |
| `/source` | Get the bot source code link (PM only) |
| `/privacy` | View the bot privacy policy |
| `/donate` | View donation info |
| `/markdownhelp` | Show markdown formatting guide |
| `/formathelp` | Show filling/format variable guide |

---

### Admins

| Command | Aliases | Description | Permission Required |
|---------|---------|-------------|---------------------|
| `/pin [notify\|loud]` | — | Pin a replied message | Can Pin |
| `/unpin [all]` | — | Unpin the last or all pinned messages | Can Pin |
| `/setgpic` | — | Set group photo from replied image | Can Change Info |
| `/adminlist` | — | List all group admins | — |
| `/promote` | — | Promote a user to admin | Can Promote |
| `/demote` | — | Demote an admin | Can Promote |
| `/zombies` | — | Kick all deleted accounts from the group | Can Restrict |

---

### Backups

| Command | Description | Permission Required |
|---------|-------------|---------------------|
| `/backup` | Backup all plugin data for this chat | Admin Only |
| `/restore` | Restore plugin data from a backup file (reply to file) | Admin Only |

---

### Federations

| Command | Aliases | Description |
|---------|---------|-------------|
| `/newfed <name>` | — | Create a new federation (PM only) |
| `/delfed` | — | Delete your federation (PM only) |
| `/joinfed <fed_id>` | — | Join a federation in this chat |
| `/leavefed` | — | Leave the current federation |
| `/fedpromote <user>` | `/fpromote` | Promote a user to federation admin |
| `/feddemote <user>` | `/fdemote` | Demote a federation admin |
| `/fedinfo [fed_id]` | — | Get info about a federation |
| `/fedadmins [fed_id]` | `/fedadmin`, `/fadmin`, `/fadmins` | List federation admins |
| `/fban <user> [reason]` | — | Federation-ban a user |
| `/unfban <user>` | — | Remove a federation ban |
| `/fbanstats` | `/fstats`, `/fedstats` | Get federation ban stats for a user |
| `/fedbackup` | — | Backup federation ban list (PM only) |
| `/fedrestore` | — | Restore federation bans from backup (PM only) |
| `/myfed` | `/myfeds` | Show your federation info (PM only) |
| `/setfedlog <fed_id>` | — | Set a channel as federation log |
| `/unsetfedlog` | — | Remove the federation log channel |
| `/subfed <fed_id>` | — | Subscribe this federation to another |
| `/unsubfed <fed_id>` | — | Unsubscribe from a federation |

---

### Filters

| Command | Aliases | Description | Permission Required |
|---------|---------|-------------|---------------------|
| `/filter <keyword> <reply or text>` | — | Add a keyword auto-reply filter | Admin Only |
| `/stop <keyword>` | — | Remove a filter | Admin Only |
| `/rmallfilter` | `/rmallfilters` | Remove all filters in this chat | Admin Only |
| `/filters` | — | List all active filters | Admin Only |

---

### Language

| Command | Aliases | Description |
|---------|---------|-------------|
| `/setlang [code]` | `/lang`, `/language` | Set the bot language for this chat (en, id, de) |

---

### Lockings

| Command | Aliases | Description | Permission Required |
|---------|---------|-------------|---------------------|
| `/lock <type>` | — | Lock a message type in the chat | Admin Only |
| `/unlock <type>` | — | Unlock a message type | Admin Only |
| `/locktypes` | — | List all available lock types | Admin Only |
| `/list_locks` | `/listlocks`, `/locks`, `/locked`, `/locklist` | Show current lock status | Admin Only |

**Lock types include:** `audio`, `animation`, `document`, `forward`, `photo`, `sticker`, `video`, `contact`, `location`, `venue`, `game`, `dice`, `button`, `inline`, `url`, `bots`, `rtl`, `anon`, `messages`, `media`, `polls`, `previews`, `info`, `invite`, `pin`, and more.

---

### Misc

| Command | Description |
|---------|-------------|
| `/id` | Show IDs for chat, message, user, or media |
| `/paste [service]` | Paste text/document to a paste service |
| `/slap` | Slap a user with a neko animation |
| `/source` | Get source code link (PM only) |

---

### Muting

| Command | Description | Permission Required |
|---------|-------------|---------------------|
| `/mute [user] [duration]` | Mute a user (e.g. `1h`, `30m`, `60s`) | Can Restrict |
| `/unmute [user]` | Unmute a user | Can Restrict |

---

### Notes

| Command | Aliases | Description | Permission Required |
|---------|---------|-------------|---------------------|
| `/save <name> <content>` | — | Save a note | Admin Only |
| `/get <name>` | — | Retrieve a note | — |
| `/notes` | — | List all saved notes | — |
| `/delnote <name>` | `/clear` | Delete a note | Admin Only |
| `#notename` | — | Trigger a note by hashtag | — |

---

### Purges

| Command | Aliases | Description | Permission Required |
|---------|---------|-------------|---------------------|
| `/del` | — | Delete a replied message | Can Delete |
| `/purge` | `/prune` | Purge messages from replied message to current | Can Delete |

---

### Reporting

| Command | Description | Permission Required |
|---------|-------------|---------------------|
| `/report` | Report a replied message to admins | — |
| `/reports [on\|off]` | Toggle report notifications for yourself or the chat | Admin Only |
| `@admin` / `@admins` | Mention all admins and report a message | — |

---

### Restrictions

| Command | Aliases | Description | Permission Required |
|---------|---------|-------------|---------------------|
| `/ban [user] [reason]` | — | Ban a user | Can Restrict |
| `/sban [user]` | — | Silently ban a user (deletes command) | Can Restrict |
| `/unban [user]` | — | Unban a user | Can Restrict |
| `/kick [user] [reason]` | — | Kick a user | Can Restrict |
| `/warn [user] [reason]` | — | Warn a user | Can Restrict |
| `/warns` | — | View warns for a user | — |
| `/rmwarn [user]` | `/removewarn` | Remove the latest warn from a user | Can Restrict |
| `/warnlimit <number>` | `/warnlim` | Set the warn threshold before auto-ban | Admin Only |

---

### Rules

| Command | Description | Permission Required |
|---------|-------------|---------------------|
| `/setrules <text>` | Set the group rules | Admin Only |
| `/clearrules` | Clear the group rules | Admin Only |
| `/rules` | View the group rules | — |

---

### Spam Shield

| Command | Description | Permission Required |
|---------|-------------|---------------------|
| `/spamshield [on\|off]` | Enable or disable SpamShield for this chat | Admin Only |

SpamShield automatically bans users flagged by [CAS](https://cas.chat), [SpamWatch](https://t.me/SpamWatch), or Anjani's internal spam prediction.

---

### Greetings (Welcome)

| Command | Description | Permission Required |
|---------|-------------|---------------------|
| `/setwelcome <text>` | Set a custom welcome message | Admin Only |
| `/resetwelcome` | Reset welcome message to default | Admin Only |
| `/welcome [on\|off\|noformat]` | Toggle or view the welcome message | Admin Only |
| `/setgoodbye <text>` | Set a custom goodbye message | Admin Only |
| `/resetgoodbye` | Reset goodbye message to default | Admin Only |
| `/goodbye [on\|off\|noformat]` | Toggle or view the goodbye message | Admin Only |
| `/cleanservice [on\|off]` | Auto-delete join/leave service messages | Admin Only |

**Welcome message variables:**

| Variable | Description |
|----------|-------------|
| `{first}` | User's first name |
| `{last}` | User's last name |
| `{fullname}` | User's full name |
| `{username}` | User's username |
| `{mention}` | Mention the user |
| `{id}` | User's ID |
| `{count}` | Member count |
| `{chatname}` | Chat title |

---

### Staff Tools *(restricted)*

| Command | Description | Access |
|---------|-------------|--------|
| `/broadcast <message>` | Broadcast a message to all chats | Owner Only |
| `/leavechat <chat_id>` | Make the bot leave a chat | Staff Only |
| `/chatlist` | Get a list of all chats the bot is in | Staff Only |
| `/logs` | Send the bot log file | Dev Only (PM) |
| `/eval <code>` | Evaluate Python code | Dev Only |
| `/stats [reset]` | View bot statistics | Dev Only (PM) |

---

## Supported Languages

| Code | Language |
|------|----------|
| `en` | 🇺🇸 English |
| `id` | 🇮🇩 Indonesian |
| `de` | 🇩🇪 German |

---

## License

[GPL-3.0](LICENSE)
