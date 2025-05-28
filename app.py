from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from flask import Flask, request, jsonify
import os

# Initialize Flask app
app = Flask(__name__)

# Slack bot token (Use environment variables for better security)
slack_token = os.getenv("SLACK_BOT_TOKEN")  # Replace with your environment variable for security
client = WebClient(token=slack_token)

# Slack event listener endpoint
@app.route("/slack/events", methods=["POST"])
def slack_events():
    event_data = request.json

    # Handle URL verification (Slack sends this to verify the URL)
    if event_data.get("type") == "url_verification":
        return jsonify({"challenge": event_data["challenge"]})

    # Process the incoming message event
    if "event" in event_data:
        event = event_data["event"]
        user_message = event.get("text")
        channel = event.get("channel")  # The DM channel

        # Check if the message is from the bot itself and ignore it
        if "subtype" not in event:  # This means it's not a bot's message
            if user_message:
                try:
                    # Send the same message back to the user in the same DM
                    response = client.chat_postMessage(
                        channel=channel,  # The DM channel
                        text=f"Echo: {user_message}"  # Respond with the same message
                    )
                except SlackApiError as e:
                    return jsonify({"error": f"Slack API error: {e.response['error']}"})

    return jsonify({"status": "ok"})


# Run the Flask app (on Render, this will be handled by Gunicorn)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
