from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from flask import Flask, request, jsonify
import os

# Initialize Flask app
app = Flask(__name__)

# Slack bot token (use environment variables for security)
slack_token = os.getenv("SLACK_BOT_TOKEN")  # Assuming the token is stored as an env variable
client = WebClient(token=slack_token)

@app.route("/slack/events", methods=["POST"])
def slack_events():
    event_data = request.json
    print("Received event data:", event_data)  # Debug log to check what Slack is sending

    # Handle URL verification (Slack sends this to verify the URL)
    if event_data.get("type") == "url_verification":
        print("URL verification challenge:", event_data["challenge"])  # Debug challenge
        return jsonify({"challenge": event_data["challenge"]})

    # Process incoming message event (e.g., user sends a message to bot)
    if "event" in event_data:
        event = event_data["event"]
        user_message = event.get("text")
        channel = event.get("channel")

        # Check if the message is from the bot itself and ignore it
        if "subtype" not in event:  # This means it's not a bot's message
            if user_message:
                try:
                    print(f"Sending response to channel {channel} with message: {user_message}")  # Debug message
                    # Send the same message back to the user in the same DM
                    response = client.chat_postMessage(
                        channel=channel,  # The DM channel
                        text=f"Echo: {user_message}"  # Respond with the same message
                    )
                    print("Response sent:", response)  # Debug log to ensure response is sent
                except SlackApiError as e:
                    print(f"Error sending message: {e.response['error']}")  # Print error in case of failure
                    return jsonify({"error": f"Slack API error: {e.response['error']}"})

    return jsonify({"status": "ok"})


# Run the Flask app (on Render, this will be handled by Gunicorn)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
