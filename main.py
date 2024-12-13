from flask import Flask, request, jsonify
import requests
import sqlite3
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from threading import Thread
import os
app = Flask(__name__)
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
# Slack Bot Token and Signing Secret
SLACK_BOT_TOKEN =SLACK_BOT_TOKEN 
client = WebClient(token=SLACK_BOT_TOKEN)

# Dependency API URL
PRODUCTS_API_URL = "https://fakestoreapi.com/products"

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect("queries.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS queries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        price_range TEXT
    )''')
    conn.commit()
    conn.close()

init_db()
@app.route("/", methods=["GET"])
def geteee():
    return "its wotking"
@app.route("/products", methods=["GET"])
def get_products():
    """
    REST API to filter products by price range and limit.
    """
    price_min = request.args.get("price_min", type=float, default=0)
    price_max = request.args.get("price_max", type=float, default=float("inf"))
    limit = request.args.get("limit", type=int, default=10)

    # Fetch products from the dependency API
    response = requests.get(PRODUCTS_API_URL)
    if response.status_code != 200:
        return jsonify({"error": "Failed to fetch products."}), 500

    products = response.json()

    # Filter products by price range
    filtered_products = [
        product for product in products
        if price_min <= product["price"] <= price_max
    ][:limit]

    # Find the lowest price product
    lowest_price_product = min(filtered_products, key=lambda x: x["price"], default=None)
    print(lowest_price_product)
    # Send the lowest price product to Slack
    if lowest_price_product:
        try:
            client.chat_postMessage(
                channel="#msmmm",
                text=f"Lowest Price Product: {lowest_price_product} - ${lowest_price_product['price']}\nDescription: {lowest_price_product['description']}"
            )
        except SlackApiError as e:
            return jsonify({"error": str(e)}), 500

    return jsonify(filtered_products)


@app.route("/slack/command", methods=["POST"])
def slack_command():
    """
    Handle Slack commands with an immediate response.
    """
    data = request.form
    user_id = data.get("user_id")
    text = data.get("text")  # e.g., "price_min=10 price_max=50 limit=5"

    # Parse parameters from the Slack command input
    try:
        params = dict(param.split("=") for param in text.split())
        price_min = float(params.get("price_min", 0))
        price_max = float(params.get("price_max", float("inf")))
        limit = int(params.get("limit", 10))
    except Exception:
        return jsonify({
            "response_type": "ephemeral",
            "text": "Invalid parameters. Use: price_min=VALUE price_max=VALUE limit=VALUE"
        })

    # Respond immediately to Slack
    response_text = "Fetching products for your query. This may take a few seconds..."
    Thread(target=process_slack_command, args=(user_id, price_min, price_max, limit)).start()

    return jsonify({
        "response_type": "ephemeral",  # Or "in_channel" if needed
        "text": response_text
    })


def process_slack_command(user_id, price_min, price_max, limit):
    """
    Process the Slack command asynchronously.
    """
    try:
        # Call the get_products function
        with app.test_request_context(
            f"/products?price_min={price_min}&price_max={price_max}&limit={limit}"
        ):
            response = get_products()

        # Handle the response from get_products
        if response.status_code == 200:
            products = response.get_json()
            if products:
                product_list = "\n".join([
                    f"*{product['title']}* - ${product['price']}\n>{product['description']}"
                    for product in products
                ])
                message = f"Products within your range:\n{product_list}"
            else:
                message = "No products found in this range."
        else:
            message = "Failed to fetch products. Please try again later."

        # Send the result back to Slack
        client.chat_postMessage(
            channel="#msmmm",  # Replace with dynamic user/channel if needed
            text=message
        )
    except Exception as e:
        client.chat_postMessage(
            channel="#msmmm",
            text=f"An error occurred while processing your request: {str(e)}"
        )
if __name__ == "__main__":
    app.run(debug=False)
