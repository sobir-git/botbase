# BotBase

A lightweight async-first chatbot framework for building bots with persistent conversation state, event-driven architecture, and flexible channel integration.

## Features

- **Conversation Persistence:** Store and retrieve conversation events.
- **Event Handling:** Register handlers via decorators.
- **Flexible Channels:** Use webhooks, interactive shell, and easily add more channels.
- **Async-First Design:** Built with FastAPI and Uvicorn for high performance.
- **Configuration via YAML:** Configure your tracker backend, channels, and more.

## Installation

```bash
pip install git+https://github.com/sobir-git/botbase.git
```

For development:
```bash
git clone https://github.com/sobir-git/botbase.git
cd botbase

# Install Poetry if you haven't already
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install
```

## Usage

1. Create a `config.yml` file:

```yaml
tracker: "jsonl"
jsonl:
  file_path: "./conversation_events.jsonl"
channels:
  - type: webhook
    token: "secret-token"
    url: ""  # URL to send bot events to
```

2. Create a file (e.g. `main.py`):

```python
from botbase import botapi
from botbase.events import handler
from botbase.tracker import ConversationTracker

@handler()
async def my_handler(tracker: ConversationTracker):
    last = tracker.last_user_message()
    if last and last.text.lower() == "hello":
        tracker.send_bot_message("Hi there!")
    else:
        tracker.send_bot_message("Echo: " + (last.text if last else ""))

if __name__ == '__main__':
    botapi.runserver(host="0.0.0.0", port=8000)
```

3. Run the bot:

```bash
# Run with webhook channel
python main.py

# Run in interactive mode (command-line interface)
python main.py --interactive
```

Alternatively, you can run it with Uvicorn:

```bash
uvicorn main:botapi.app --reload
```

### **Send a Test Message**

When running with webhook channel, you can test it using curl:
```bash
curl -X POST http://localhost:8000/webhook/webhook/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer secret-token" \
  -d '{"conv_id": "test-convo-123", "text": "hello"}'
```

You should get the following response:

```json
{"conv_id":"test-convo-123","status":"Message received."}
```


## Development

### Setup

1. **Install dependencies:**
   ```bash
   poetry install
   ```

2. **Set up pre-commit hooks:**
   ```bash
   poetry run pre-commit install
   ```

### Code Style

This project uses several tools to maintain code quality:

- **Black**: Code formatting
- **isort**: Import sorting
- **Ruff**: Fast Python linter
- **pre-commit**: Automated code quality checks

Run formatters manually:
```bash
poetry run black .
poetry run isort .
poetry run ruff check --fix
```

### Testing

Run the test suite:
```bash
poetry run pytest
```

Or with coverage:
```bash
poetry run pytest --cov=botbase
```

## Publishing

For maintainers only:

1. **Build the package:**
   ```bash
   poetry build
   ```

2. **Test the build locally:**
   ```bash
   pip install dist/*.whl
   ```

3. **Publish to GitHub:**
   ```bash
   git tag v$(poetry version -s)
   git push origin v$(poetry version -s)
   ```

## License

[MIT License](LICENSE)
