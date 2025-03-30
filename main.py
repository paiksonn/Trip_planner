import requests
from urllib.parse import quote
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

TOKEN_AVIASALES = "NO NO NO mister"

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)


# --- Validation Functions ---
async def is_valid_date(date_str: str, is_end_date=False) -> bool:
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
        today = datetime.now().date()
        return date >= today
    except ValueError:
        return False
    
async def is_valid_city(city_name: str) -> bool:
    return True
# TODO: add normal validation function, not google like thing
    # try:
    #     # Format query for Nominatim (replace spaces with '+')
    #     query = quote(city_name)
    #     url = f"https://nominatim.openstreetmap.org/search?city={query}&format=json"
        
    #     # Add headers to mimic a browser request (avoid 403 errors)
    #     headers = {"User-Agent": "Mozilla/5.0 (TravelBot/1.0)"}
        
    #     response = requests.get(url, headers=headers).json()
        
    #     # Check if any result matches the city name (case-insensitive)
    #     return any(city_name.lower() in result["display_name"].lower() for result in response)
    # except Exception as e:
    #     print(f"Error validating city: {e}")
    #     return False
    
    
# --- Flight-related Functions ---
async def get_iata_code(city_name: str, api_key: str) -> str:
    """Convert city name to IATA code using Travelpayouts API."""
    try:
        response = requests.get(
            "https://api.travelpayouts.com/data/en/cities.json",
            headers={"X-Access-Token": api_key}
        ).json()
        for city in response:
            if city["name"].lower() == city_name.lower():
                return city["code"]
        return ""  # Not found
    except Exception as e:
        logger.error(f"Error fetching IATA code: {e}")
        return ""
    
async def get_iata_codes(context: ContextTypes.DEFAULT_TYPE) -> tuple:
    """Get IATA codes for both cities."""
    origin_iata = await get_iata_code(context.user_data["current_city"], TOKEN_AVIASALES)
    destination_iata = await get_iata_code(context.user_data["destination"], TOKEN_AVIASALES)
    return origin_iata, destination_iata    
    
async def fetch_flights(origin_iata: str, destination_iata: str, 
                      departure_date: str, return_date: str) -> list:
    """Fetch flights from Aviasales API."""
    try:
        params = {
            "origin": origin_iata,
            "destination": destination_iata,
            "departure_at": departure_date,
            "return_at": return_date,
            "currency": "RUB",
            "sorting": "price",
            "one_way": False,
            "direct": True,
            "limit": 5,
            "token": TOKEN_AVIASALES,
        }
        response = requests.get(
            "https://api.travelpayouts.com/aviasales/v3/prices_for_dates",
            params=params
        ).json()
        return response.get("data", [])
    except Exception as e:
        logger.error(f"Error fetching flights: {e}")
        return []    
    
async def display_flights(update: Update, flights: list) -> None:
    """Format and display flight results."""
    if not flights:
        await update.message.reply_text("🚫 No flights found for the given dates. Try different dates or cities.")
        return

    message = "✈️ *Top Flights Found:*\n"
    for flight in flights:
        message += (
            f"\n• *{flight['airline']} {flight['flight_number']}*\n"
            f"  _Departure:_ {flight['departure_at']}\n"
            f"  _Departure:_ {flight['return_at']}\n"
            f"  _Duration_to:_ {flight['duration_to']}\n"
            f"  _Duration_back:_ {flight['duration_back']}\n"
            f"  _Price:_ {flight['price']} RUB\n"
            f"  [Book Here](https://www.aviasales.com/{flight['link']})\n"
        )
    await update.message.reply_text(message, parse_mode="Markdown")



# --- Conversation Handlers ---

# Define conversation states
START_DATE, END_DATE, CURRENT_CITY, DESTINATION = range(4)

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🌍 Welcome to your Travel Assistant Bot! Use /plan_trip to start planning your vacation."
    )

async def plan_trip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "📅 Please enter your vacation START date (YYYY-MM-DD, e.g., 2025-10-28):"
    )
    return START_DATE

async def handle_start_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text
    if not await is_valid_date(user_input):
        await update.message.reply_text("❌ Invalid date. Use YYYY-MM-DD format and ensure it's not in the past. Try again:")
        return START_DATE
    
    context.user_data["start_date"] = user_input
    await update.message.reply_text("📅 Now enter your vacation END date (YYYY-MM-DD):")
    return END_DATE

async def handle_end_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text
    start_date = datetime.strptime(context.user_data["start_date"], "%Y-%m-%d").date()
    
    if not await is_valid_date(user_input):
        await update.message.reply_text("❌ Invalid date. Use YYYY-MM-DD format and ensure it's not in the past. Try again:")
        return END_DATE
    
    end_date = datetime.strptime(user_input, "%Y-%m-%d").date()
    if end_date < start_date:
        await update.message.reply_text("❌ End date must be AFTER start date. Try again:")
        return END_DATE
    
    context.user_data["end_date"] = user_input
    await update.message.reply_text("🏠 Now enter your CURRENT city (e.g., Moscow):")
    return CURRENT_CITY

async def handle_current_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    city = update.message.text
    if not await is_valid_city(city):
        await update.message.reply_text(f"❌ City '{city}' not found. Try again (e.g., Moscow):")
        return CURRENT_CITY  # Re-ask

    # TODO: add function to auto detect user IP and suggest nearest airoport https://support.travelpayouts.com/hc/en-us/articles/205895898-How-to-determine-the-user-s-location-by-IP-address
    context.user_data["current_city"] = city
    await update.message.reply_text("✈️ Now enter your DESTINATION city:")
    return DESTINATION

async def handle_destination(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    destination_city = update.message.text
    
    if not await is_valid_city(destination_city):
        await update.message.reply_text(f"❌ City '{destination_city}' not found. Try again:")
        return DESTINATION

    context.user_data["destination"] = destination_city
    return await process_flight_request(update, context)

async def process_flight_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle flight data processing after destination is confirmed."""
    origin_iata, destination_iata = await get_iata_codes(context)
    
    if not origin_iata or not destination_iata:
        await update.message.reply_text("❌ Could not find flight routes for these cities. Try another pair.")
        return ConversationHandler.END

    flights = await fetch_flights(
        origin_iata=origin_iata,
        destination_iata=destination_iata,
        departure_date=context.user_data["start_date"],
        return_date=context.user_data["end_date"]
    )

    await display_flights(update, flights)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("🚫 Trip planning canceled.")
    return ConversationHandler.END

def main() -> None:
    application = Application.builder().token("NO NO NO mister").build()

    # Conversation handler for /plan_trip
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("plan_trip", plan_trip)],
        states={
            START_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_start_date)],
            END_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_end_date)],
            CURRENT_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_current_city)],
            DESTINATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_destination)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == "__main__":
    main()
