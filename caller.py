import asyncio
from binance import AsyncClient, BinanceSocketManager
from twilio.rest import Client

# Глобальная переменная для хранения последней зафиксированной цены
last_price = None

# Twilio настройки
TWILIO_ACCOUNT_SID = "ваш_account_sid"
TWILIO_AUTH_TOKEN = "ваш_auth_token"
TWILIO_PHONE_NUMBER = "ваш_twilio_number"
USER_PHONE_NUMBER = "ваш_номер_получателя"  # Номер телефона, куда будет звонок

API_KEY = "ваш_api_key"
API_SECRET = "ваш_api_secret"

# Функция для выполнения звонка
def make_call(message):
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    call = client.calls.create(
        to=USER_PHONE_NUMBER,
        from_=TWILIO_PHONE_NUMBER,
        twiml=f"<Response><Say>{message}</Say></Response>"
    )
    print(f"Звонок выполнен: SID {call.sid}")

async def monitor_price(asset, threshold, user_id, context):
    global last_price
    try:
        client = await AsyncClient.create(API_KEY, API_SECRET)
        bsm = BinanceSocketManager(client)
        ts = bsm.trade_socket(asset)  # WebSocket for asset price tracking

        async with ts as tscm:
            print("Monitoring prices...")
            async for msg in tscm:
                current_price = float(msg['p'])

                if last_price is None:
                    last_price = current_price
                    print(f"Initial price recorded: {last_price}")
                    continue

                price_change = ((current_price - last_price) / last_price) * 100
                print(f"Current price: {current_price}, Change: {price_change:.2f}%")

                if abs(price_change) >= threshold:
                    alert_message = f"🚨 Price Alert 🚨\n{asset} changed by {price_change:.2f}%!"
                    print(alert_message)
                    make_call(alert_message)  # Call user
                    await context.bot.send_message(chat_id=user_id, text=alert_message)
                    last_price = current_price  # Update last price
                await asyncio.sleep(1)
                    
    except Exception as e:
        error_message = f"Error connecting to Binance: {e}"
        print(error_message)
        await context.bot.send_message(chat_id=user_id, text=error_message)
        return error_message  # Return the error message as a string