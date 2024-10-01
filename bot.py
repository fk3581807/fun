import os
import requests
from bs4 import BeautifulSoup
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from flask import Flask, request

# Constant for Shareus API key
SHAREUS_API_KEY = "N5WHqC160Uh4Mdp2WrRjieFPfEg1"
# Hardcoded bot token
BOT_TOKEN = "7828698807:AAEv60Zf4H086_t8kRW-xobj-tvEkfI8LCY"

# Flask web server
app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    update = request.get_json()
    if update:
        # Process the update here
        process_update(update)
    return '', 200  # Respond with 200 OK

@app.route('/')
def home():
    return "Bot is running!"

def shorten_url(long_url: str) -> str:
    """Shorten a given URL using the Shareus API."""
    api_url = f"https://api.shareus.io/easy_api?key={SHAREUS_API_KEY}&link={long_url}"
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        shortened_url = response.text.strip()
        return shortened_url if shortened_url else long_url
    except requests.exceptions.RequestException as e:
        print(f"Error shortening URL: {e}")
        return long_url

def clean_title(title: str) -> str:
    """Remove unwanted parts like '- mkvCinemas' or '.mkv' from the title."""
    cleaned_title = re.sub(r"(- mkvCinemas|\s*- mkvCinemas\.mkv|\.mkv)", "", title, flags=re.IGNORECASE)
    return cleaned_title.strip()

def search_site(keyword: str) -> list:
    """Search for movies based on the given keyword and return results."""
    search_url = f"https://mkvcinemas.cat/?s={keyword.replace(' ', '+')}"
    try:
        response = requests.get(search_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        results = soup.find_all('a', class_='ml-mask jt')

        # Extract the title and URL from each result, and clean the title
        result_texts = []
        for result in results:
            title = result.find('h2').get_text().strip()
            if "All Parts Collection" not in title:
                cleaned_title = clean_title(title)
                url = result['href']
                result_texts.append((cleaned_title, url))
        
        return result_texts[:7]  # Limit to the first 7 results
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching results: {e}")
        return []

def get_download_links(movie_url: str) -> str:
    """Fetch download links from the movie's page."""
    try:
        response = requests.get(movie_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        download_links = []
        links = soup.find_all('a', class_='gdlink') + soup.find_all('a', class_='button')

        for link in links:
            if 'gdlink' in link['class']:
                title = link['title']
            elif 'button' in link['class']:
                title = link.get_text(strip=True)

            download_url = link['href']
            cleaned_title = clean_title(title)
            shortened_url = shorten_url(download_url)
            download_links.append(f"{cleaned_title}: {shortened_url}")
        
        return "\n".join(download_links) if download_links else "No download links found."
    
    except requests.exceptions.RequestException as e:
        return f"Error fetching download links: {e}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the /start command is issued."""
    await update.message.reply_text("Welcome! Please enter a movie title to search.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user messages and store search results."""
    keyword = update.message.text.strip()
    search_results = search_site(keyword)

    if search_results:
        context.user_data['search_results'] = search_results
        
        # Create buttons for each result, using indices as callback_data
        keyboard = [
            [InlineKeyboardButton(title, callback_data=str(idx))]
            for idx, (title, _) in enumerate(search_results)
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text("Select a movie to get the download links:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("No results found. Please try again.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button clicks (user selects a movie)."""
    query = update.callback_query
    await query.answer()

    # Get the index from callback_data
    selection_idx = int(query.data)
    
    # Retrieve the corresponding URL using the index
    selected_title, selected_url = context.user_data['search_results'][selection_idx]
    
    download_links = get_download_links(selected_url)
    
    await query.edit_message_text(f"Download Links for {selected_title}:\n{download_links}")

def process_update(update: dict) -> None:
    """Process incoming updates from Telegram."""
    # Here you can implement the logic to handle different types of updates.
    # For simplicity, let's just handle the /start command and text messages.
    if 'message' in update:
        message = update['message']
        if 'text' in message:
            text = message['text']
            # Handle the message (implement the logic accordingly)
            # For example, you can check for /start command or process normal text messages
            print(f"Received message: {text}")

def main() -> None:
    """Start the bot and web server."""
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))  # Handles button clicks

    # Set the webhook URL
    webhook_url = f"https:/fun.vercel.app/webhook"  # Replace with your actual Vercel URL
    application.run_webhook(listen='0.0.0.0', port=int(os.environ.get("PORT", 8443)), url_path=BOT_TOKEN)

if __name__ == '__main__':
    main()
