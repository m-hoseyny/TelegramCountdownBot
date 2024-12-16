# Telegram Countdown Bot

A Telegram bot that manages countdown timers in channels with customizable message templates and Persian number support.

## Features

- 🕒 Create countdowns with Persian timestamps
- 📝 Customizable message templates with HTML support
- 🔄 Auto-updates every 10 seconds
- 🔢 Persian number display
- 📸 Supports both text messages and media captions
- 💾 Persistent storage of countdowns
- 🐳 Docker support for easy deployment

## Test Bot

You can test the functionality using [@CountDownChannelBot](https://t.me/CountDownChannelBot)

## Setup

### Prerequisites

- Python 3.11+
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)
- Docker (optional)

### Installation

1. Clone the repository:
```bash
git clone [repository-url]
cd TelegramCountdownBot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

### Running with Docker

1. Set your bot token:
```bash
export TOKEN=your_bot_token_here
```

2. Build and run with Docker Compose:
```bash
docker-compose up -d
```

### Running without Docker

1. Set your bot token:
```bash
export TOKEN=your_bot_token_here
```

2. Run the bot:
```bash
python TeleCountDownBot.py
```

## Usage

1. Add the bot to your channel as an admin
2. Start a private chat with the bot
3. Send `/start_countdown` to begin setting up a countdown
4. Follow the bot's instructions:
   - Send the message link from your channel
   - Specify the target date and time in Persian format (e.g., `1403-12-29 23:59:59`)
   - Provide a message template using the available placeholders

### Message Template Placeholders

- `{days}` - Days remaining
- `{hours}` - Hours remaining
- `{minutes}` - Minutes remaining
- `{seconds}` - Seconds remaining

### Example Template

```
⏰ {days} روز و {hours} ساعت و {minutes} دقیقه و {seconds} ثانیه تا یلدا
```

## Features

- HTML formatting support in messages
- Automatic Persian number conversion
- Support for both text messages and media captions
- Persistent storage of countdowns in JSON format
- Error notifications to admin
- Automatic cleanup of expired countdowns

## Requirements

- python-telegram-bot==21.6
- persiantools==3.0.1
- APScheduler==3.10.4

## Error Handling

- The bot automatically detects if a message has text or caption and adjusts accordingly
- If a message is deleted, the countdown is automatically removed
- Admins receive error notifications for any issues

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
