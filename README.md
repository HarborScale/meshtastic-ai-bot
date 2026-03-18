# Meshtastic AI Bot

An AI-powered bot that connects to Meshtastic devices and responds to queries using OpenAI's GPT models.

## Features

- Connects to Meshtastic devices via serial/USB
- Listens for messages starting with a configurable prefix (default: `!`)
- Sends queries to OpenAI's GPT-4o-mini model
- Automatically limits responses to fit Meshtastic's character constraints
- Cross-platform GUI built with [DearPyGui](https://github.com/hoffstadt/DearPyGui) — works on Windows, macOS, and Linux
- Real-time message logging

## Requirements

- Python 3.8+
- A Meshtastic device connected via USB
- An OpenAI API key

## Setup

1. Clone the repo and install dependencies:

   ```bash
   git clone https://github.com/HarborScale/meshtastic-ai-bot.git
   cd meshtastic-ai-bot
   pip install -r requirements.txt
   ```

2. Connect your Meshtastic device via USB.

3. Run the application:

   ```bash
   python meshtastic_ai_bot.py
   ```

4. Configure the bot in the GUI:
   - Select your COM port from the dropdown and click **Connect**
   - Enter your OpenAI API key and click **Enable AI**
   - Click **Start Bot**

## Usage

Once the bot is running, anyone on the mesh network can send a message starting with `!` followed by their question:

```
!How do I fix a flat tire?
!Tell me a joke
```

The bot will respond with an AI-generated answer trimmed to the configured character limit.

## Configuration

| Setting | Default | Description |
|---|---|---|
| **Command Prefix** | `!` | Trigger character(s) for the bot |
| **Max Response Length** | `200` | Character cap for outgoing messages |
| **OpenAI Model** | `gpt-4o-mini` | Fast, cost-effective model used for responses |

## Dependencies

| Package | Purpose |
|---|---|
| `meshtastic` | Communicate with Meshtastic devices |
| `pyserial` | Serial port access |
| `PyPubSub` | Event-based message subscription |
| `openai` | OpenAI API client |
| `dearpygui` | Cross-platform GUI |

## License

MIT
