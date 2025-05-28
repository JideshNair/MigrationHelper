import os
import replicate
import logging
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from flask import Flask, request, jsonify

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Slack bot token (use environment variables for security)
slack_token = os.getenv("SLACK_BOT_TOKEN")
client = WebClient(token=slack_token)

# Replicate API token (set as environment variable for security)
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

# Set up Replicate API client
replicate.Client(api_token=REPLICATE_API_TOKEN)

# Function to call Replicate's model
def generate_image_from_replicate(prompt):
    logger.info(f"Calling Replicate API with prompt: {prompt}")
    
    try:
        output = replicate.run(
            "jideshnair/inspirevision:b7a5791fc35a49b798f8e4c7bd6200b1f59a7db888aea026b7d86e8e6cae0bac",
            input={
                "model": "dev",
                "prompt": prompt,
                "go_fast": False,
                "lora_scale": 1,
                "megapixels": "1",
                "num_outputs": 1,
                "aspect_ratio": "1:1",
                "output_format": "webp",
                "guidance_scale": 3,
                "output_quality": 80,
                "prompt_strength": 0.8,
                "extra_lora_scale": 1,
                "num_inference_steps": 28
            }
        )
        logger.info(f"Replicate API response: {output}")
        return output  # The URL of the generated image
    except Exception as e:
        logger.error(f"Error calling Flux LoRA API: {e}")
        return None

@app.route("/slack/events", methods=["POST"])
def slack_events():
    event_data = request.json
    logger.debug(f"Received event data: {event_data}")

    # Handle URL verification (Slack sends this to verify the URL)
    if event_data.get("type") == "url_verification":
        logger.info(f"URL verification challenge: {event_data['challenge']}")
        return jsonify({"challenge": event_data["challenge"]})

    # Process incoming message event (e.g., user sends a message to bot)
    if "event" in event_data:
        event = event_data["event"]
        user_message = event.get("text")
        channel = event.get("channel")
        user = event.get("user")
        
        logger.info(f"Processing event from user {user}: {user_message}")

        # Ignore bot's own messages (subtype: 'bot_message')
        if event.get("subtype") == "bot_message":
            logger.info("Ignoring bot's own message.")
            return jsonify({"status": "ok"})  # Don't respond if the message is from the bot

        if user_message:
            logger.info(f"Received user message: {user_message}")
            
            # Call Replicate to generate an image from the message
            image_url = generate_image_from_replicate(user_message)

            if image_url:
                try:
                    # Send the URL of the generated image back to the user in the same DM
                    response = client.chat_postMessage(
                        channel=channel,  # The DM channel
                        text=f"Here is your generated image: {image_url}"  # Send the URL as the response
                    )
                    logger.info(f"Message sent to Slack: {response}")
                except SlackApiError as e:
                    logger.error(f"Error sending message: {e.response['error']}")
                    return jsonify({"error": f"Slack API error: {e.response['error']}"})

    return jsonify({"status": "ok"})


# Run the Flask app (on Render, this will be handled by Gunicorn)
if __name__ == "__main__":
    logger.info("Starting Flask app...")
    app.run(host="0.0.0.0", port=5000, debug=True)
