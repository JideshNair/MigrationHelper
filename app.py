import os
import replicate
import logging
import threading
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from flask import Flask, request, jsonify

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

slack_token = os.getenv("SLACK_BOT_TOKEN")
client = WebClient(token=slack_token)

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
replicate.Client(api_token=REPLICATE_API_TOKEN)

# Keep track of which Slack event_ids we've already handled
processed_event_ids = set()

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
        if output:
            url = output[0].url
            logger.info(f"Replicate API returned image URL: {url}")
            return url
        logger.error("Replicate API returned no output.")
    except Exception as e:
        logger.error(f"Error calling Replicate API: {e}")
    return None

def process_slack_event(event_data):
    event_id = event_data.get("event_id")
    # 1️⃣ Dedupe on Slack's event_id
    if event_id in processed_event_ids:
        logger.debug(f"Already processed {event_id}, skipping.")
        return
    processed_event_ids.add(event_id)

    event = event_data["event"]
    # 2️⃣ Ignore Slack retries beyond the first delivery
    #     (we already dedupe by event_id, but you can also check headers if you like)
    if event_data.get("retry_num", 0) > 0:
        return

    # 3️⃣ Ignore bot messages & edits
    if event.get("subtype") or event.get("bot_id"):
        return

    user       = event.get("user")
    text       = event.get("text", "").strip()
    channel    = event.get("channel")
    if not user or not text or not channel:
        return

    # 4️⃣ Single call → single image
    image_url = generate_image_from_replicate(text)
    if not image_url:
        return

    try:
        client.chat_postMessage(
            channel=channel,
            text=f"Here is your generated image: {image_url}"
        )
    except SlackApiError as e:
        logger.error(f"Slack API error: {e.response['error']}")

@app.route("/slack/events", methods=["POST"])
def slack_events():
    event_data = request.get_json()
    logger.debug(f"Received event data: {event_data}")

    # URL verification handshake
    if event_data.get("type") == "url_verification":
        return jsonify({"challenge": event_data["challenge"]})

    # Drop Slack retries before event processing
    # (Slack will set X-Slack-Retry-Num header to “1”, “2”, …)
    if request.headers.get("X-Slack-Retry-Num", "0") != "0":
        logger.debug("Dropping retry request from Slack")
        return jsonify({"status": "ok"})

    # ACK immediately (within 3 seconds) by returning here,
    # then do the heavy lifting in a background thread
    threading.Thread(target=process_slack_event, args=(event_data,)).start()
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    logger.info("Starting Flask app…")
    app.run(host="0.0.0.0", port=5000)
