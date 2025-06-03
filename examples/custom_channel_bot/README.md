# Creating a Custom Jivo Channel Bot

This example demonstrates how to create a custom channel for the [Jivo Chat](https://www.jivochat.com/) platform.

JivoChat Bot API documentation: [JivoChat Bot API](https://www.jivochat.com/help/api/bot-api.html)

## Setup

1. Create a `config.yml` file:
   ```yaml
   tracker: jsonl
   jsonl:
     file_path: ./conversation_events.jsonl
   channels:
     - type: channels.jivo.JivoChatChannel
       name: my_jivo_bot
       provider_id: provider001
       shared_token: jivobottoken001
   ```

2. Create a custom channel implementation in `channels/jivo.py`:
   - Implement `JivoChatChannel` class extending `BaseChannel`
   - Set up webhook endpoint to receive messages from Jivo
   - Process incoming messages and convert them to bot events
   - Handle bot responses and send them back to Jivo API

3. Create a `main.py` file with your bot logic:
   ```python
   from botbase import botapi
   from botbase.events import handler
   from botbase.tracker import ConversationTracker

   @handler()
   async def greet_user(tracker: ConversationTracker):
       last_msg = tracker.last_user_message()
       if last_msg and "hello" in last_msg.text.lower():
           tracker.send_bot_message("Hello there! How can I help you today?")

   # Add more handlers for different user inputs
   # - Button responses
   # - Markdown formatting
   # - Other specialized responses

   if __name__ == "__main__":
       botapi.runserver(host="0.0.0.0", port=8000)
   ```

4. Run the bot:
   ```bash
   python main.py
   ```

## Testing

You can test your Jivo bot by sending a webhook to your local server:

```bash
curl -X POST \
  http://localhost:8000/channels/my_jivo_bot/jivobottoken001 \
  -H 'Content-Type: application/json' \
  -d '{
    "event": "CLIENT_MESSAGE",
    "id": "evt_123abc456def789",
    "client_id": "client_user_777",
    "chat_id": "chat_session_555",
    "message": {
      "type": "TEXT",
      "text": "count 2",
      "timestamp": 1678886400
    }
  }'
```

The bot will send a response message to the JivoChat endpoint using the webhook URL format: `https://bot.jivosite.com/webhooks/{provider_id}/{shared_token}`. The message will be formatted according to the JivoChat Bot API specification, with event type "BOT_MESSAGE" containing the response text or interactive elements.
