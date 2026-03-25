# 🔴 INFLUENCE - Telegram User Monitoring Tool

<div align="center">

```
.__        _____.__                                     
|__| _____/ ____\  |  __ __   ____   ____   ____  ____  
|  |/    \   __\|  | |  |  \_/ __ \ /    \_/ ___\/ __ \ 
|  |   |  \  |  |  |_|  |  /\  ___/|   |  \  \__\  ___/ 
|__|___|  /__|  |____/____/  \___  >___|  /\___  >___  >
        \/                       \/     \/     \/    \/
```

**Advanced Telegram OSINT & Monitoring Framework**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Telethon](https://img.shields.io/badge/Telethon-Latest-green.svg)](https://github.com/LonamiWebs/Telethon)
[![License](https://img.shields.io/badge/License-MIT-red.svg)](LICENSE)

</div>

---

## 📋 Overview

**INFLUENCE** is a powerful Telegram user monitoring and OSINT tool built with Python and Telethon. Track user activity, profile changes, messages, and social interactions in real-time with an elegant CLI interface.

### ✨ Key Features

- 🎯 **Multi-Target Monitoring** - Track multiple users simultaneously
- 📊 **Real-time Activity Tracking** - Live message monitoring with instant notifications
- 👤 **Profile Change Detection** - Track username, name, photo, bio, and phone changes
- 🟢 **Status Monitoring** - Online/offline status tracking
- 🗑️ **Deleted Message Detection** - Track when messages are deleted
- 📈 **Activity Statistics** - Hourly and daily activity patterns
- 🔍 **Message Scraping** - Export all messages from common groups
- 👥 **Social Network Analysis** - View common groups and connections
- ⚙️ **Granular Settings** - Configure what to track for each target
- 💾 **Persistent Logging** - All activity saved to individual log files
- 🎨 **Beautiful CLI** - Color-coded interface with real-time updates

---

## 🚀 Installation

### Prerequisites

- Python 3.8 or higher
- Telegram API credentials (api_id and api_hash)
- Active Telegram account

### Step 1: Clone Repository

```bash
git clone https://github.com/yourusername/influence.git
cd influence
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

**Required packages:**
- `telethon` - Telegram client library
- `colorama` - Terminal color support

### Step 3: Get Telegram API Credentials

1. Go to [my.telegram.org](https://my.telegram.org)
2. Log in with your phone number
3. Navigate to "API Development Tools"
4. Create a new application
5. Copy your `api_id` and `api_hash`

---

## 🎮 Usage

### Starting the Tool

```bash
python main.py
```

On first run, you'll be prompted to enter:
- API ID
- API Hash
- Phone number (with country code)
- Session name (optional)
- Telegram verification code

### Basic Commands

| Command | Description |
|---------|-------------|
| `add @username` | Add a new target to monitor |
| `remove N` | Remove target by number |
| `switch N` | Switch to target number N |
| `list` | Show all targets |
| `logs [N]` | Show recent N logs (default: 20) |
| `stats` | Show activity statistics |
| `profile` | Show detailed profile info |
| `deleted` | Show deleted messages |
| `scrape` | Scrape messages from chats |
| `groups` | Show common groups |
| `settings` | Configure monitoring settings |
| `export` | Export logs to file |
| `clear` | Clear screen |
| `help` | Show all commands |
| `exit` | Exit program |

---

## 📖 Examples

### Adding a Target

```
└──> add @username
✓ Target added: John Doe
```

### Switching Between Targets

```
└──> switch 2
✓ Switched to: Jane Smith
```

### Viewing Statistics

```
└──> stats

=== Activity Statistics for John Doe ===

Messages per hour: 5
Messages today: 47
Total messages: 1523

Most Active Hours:
14:00 ████████████████ 156
18:00 ████████████ 98
21:00 ████████ 67
```

### Real-time Monitoring

Once a target is added, all their activity appears in real-time:

```
Hello! [24.03.2026 15:30] | msg: https://t.me/username/12345
[PROFILE] Статус → online [24.03.2026 15:31]
How are you? [24.03.2026 15:32] | msg: https://t.me/username/12346
```

---

## ⚙️ Configuration

### Monitoring Settings

Each target has individual settings that can be configured:

```
└──> settings

1. Track new messages: ON
2. Track profile changes: ON
3. Track online/offline status: ON
4. Track deleted messages: ON
5. Track media files: ON
6. Track bio/description changes: ON
7. Track phone number changes: ON
8. Track stories: ON
```

### Session Management

Sessions are saved automatically. On subsequent runs, the tool will use the saved session without requiring re-authentication.

Session files:
- `config.json` - Configuration and targets
- `{session_name}.session` - Telegram session data
- `logs/` - Individual log files for each target

---

## 📁 Project Structure

```
influence/
├── main.py                 # Main application
├── config.json            # Configuration file
├── triumph.session        # Telegram session
├── logs/                  # Target log files
│   ├── username_123.txt
│   └── ...
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

---

## 🔒 Security & Privacy

- **Session Security**: Session files contain sensitive authentication data. Keep them secure.
- **API Credentials**: Never share your API ID and API Hash publicly.
- **Legal Use**: This tool is for educational and authorized monitoring only.
- **Data Privacy**: All logs are stored locally. No data is sent to external servers.

### Censored Display

Sensitive information is automatically censored in the interface:
- API Hash: `abc...xyz`
- Phone numbers: `123.......89`

---

## 🛠️ Troubleshooting

### Common Issues

**"Session error" on startup**
- Delete the `.session` files and re-authenticate

**"FloodWaitError"**
- Telegram rate limiting. Wait the specified time before retrying.

**"No targets added"**
- Use `add @username` to add a target first

**Prompt disappears after logs**
- This is a known issue with terminal handling. Type your command and press Enter.

---

## 📊 Features in Detail

### Message Tracking
- Real-time message capture
- Direct message links
- Media detection
- Timestamp logging

### Profile Monitoring
- Username changes
- Display name changes
- Profile photo updates
- Bio/description changes
- Phone number changes
- Story additions/deletions

### Activity Analytics
- Messages per hour/day
- Most active hours
- Daily activity patterns
- Long-term statistics

### Message Scraping
- Export from common groups
- Export from specific chats
- Complete message history
- Direct message links

---

## 🤝 Contributing

Contributions are welcome! Feel free to:
- Report bugs
- Suggest features
- Submit pull requests

---

## ⚠️ Disclaimer

This tool is provided for educational and research purposes only. Users are responsible for complying with:
- Telegram's Terms of Service
- Local laws and regulations
- Privacy rights of monitored individuals

The developers assume no liability for misuse of this software.

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 👨‍💻 Author

**triumph**

---

## 🌟 Support

If you find this tool useful, please consider:
- ⭐ Starring the repository
- 🐛 Reporting bugs
- 💡 Suggesting new features

---

<div align="center">

**Made with ❤️ for the OSINT community**

</div>
