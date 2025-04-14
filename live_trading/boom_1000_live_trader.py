import pandas as pd
import numpy as np
import time
import os
import sys
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import telegram
from threading import Thread

# Boom 1000 Index Trading Parameters
SPREAD = 1.2  # Fixed spread of 1.2 points (based on spread analysis)
MIN_VOLUME = 0.2  # Minimum volume of 0.2 lots (as specified by user)
MAX_VOLUME = 50  # Maximum volume of 50 lots
VOL_LIMIT = 120  # Volume limit of 120 lots in one direction (as specified by user)
VOL_STEP = 0.01  # Volume step of 0.01 lots
POINT_VALUE = 1.0  # $1.00 per point per standard lot (at 0.1 lots, each point is worth $0.10)

# Pattern detection parameters
LOOKBACK_WINDOW = 5  # Number of bars to look back
MIN_DECLINE_PCT = 0.01  # Minimum percentage decline for V pattern
MIN_RECOVERY_PCT = 0.01  # Minimum percentage recovery for V pattern

# Optimized trading rules (from analysis)
RECOVERY_PCT_THRESHOLD = 0.0248  # Only trade patterns with recovery_pct >= this value
VELOCITY_THRESHOLD = 2.1  # Only trade patterns with bottom_to_high_velocity >= this value
RANGE_THRESHOLD = 2.1  # Only trade patterns with confirm_range <= this value

# MT5 Connection Parameters
LOGIN = 40496559  # Demo account for testing filling and position sizing
PASSWORD = "@Ripper25"
SERVER = "DerivSVG-Server-03"

# Telegram Bot Parameters
TELEGRAM_TOKEN = "7717225420:AAE5TNborRsbniBfuGc4yuPQnftSZ2Gyuvs"  # @live_vmbot
TELEGRAM_CHAT_ID = 1435296772

# Trading Parameters
SYMBOL = "Boom 1000 Index"  # Will be updated with the actual symbol name from MT5
CHECK_INTERVAL = 60  # Check for new patterns every 60 seconds
DATA_BUFFER_SIZE = 1000  # Number of bars to keep in memory

# Global variables
bot = None
last_processed_time = None
patterns_found = 0
patterns_traded = 0
current_positions = {}
trade_history = []

def setup_telegram_bot():
    """
    Set up the Telegram bot for sending notifications
    """
    global bot
    try:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        print("Telegram bot initialized successfully")
        send_telegram_message("🚀 Boom 1000 Index Live Trader started")
        return True
    except Exception as e:
        print(f"Error initializing Telegram bot: {e}")
        return False

def send_telegram_message(message):
    """
    Send a message via Telegram
    """
    if bot is None:
        print("Telegram bot not initialized")
        return False

    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode='Markdown')
        return True
    except Exception as e:
        print(f"Error sending Telegram message: {e}")
        return False

def connect_to_mt5(login, password, server):
    """
    Connect to MT5 terminal
    """
    # Ensure that MetaTrader 5 is installed
    if not mt5.initialize():
        print("initialize() failed, error code =", mt5.last_error())
        return False

    # Connect to the specified account
    authorized = mt5.login(login, password, server)
    if not authorized:
        print(f"Failed to connect to account {login}, error code: {mt5.last_error()}")
        return False

    print(f"Connected to account {login} on server {server}")

    # Get account info
    account_info = mt5.account_info()
    if account_info is not None:
        print(f"Account: {account_info.login}, Balance: ${account_info.balance}")
        send_telegram_message(f"📊 Connected to account {account_info.login}\nBalance: ${account_info.balance:.2f}")

    return True

def find_boom_1000_index_symbol():
    """
    Find the correct symbol name for Boom 1000 Index
    """
    # Get all available symbols
    symbols = mt5.symbols_get()
    print(f"Total symbols available: {len(symbols)}")

    # First try to find Boom 1000 Index directly
    for symbol in symbols:
        if "Boom" in symbol.name and "1000" in symbol.name:
            print(f"Found Boom 1000 Index symbol: {symbol.name}")
            return symbol.name

    # If exact match not found, look for any Boom symbols
    boom_symbols = []
    for symbol in symbols:
        if "Boom" in symbol.name:
            boom_symbols.append(symbol.name)

    if boom_symbols:
        print("Found these Boom symbols:")
        for i, symbol in enumerate(boom_symbols):
            print(f"{i+1}. {symbol}")

        # If there's only one Boom symbol, use it
        if len(boom_symbols) == 1:
            print(f"Using the only Boom symbol found: {boom_symbols[0]}")
            return boom_symbols[0]

    print("Could not find Boom 1000 Index symbol. Please check the symbol name in MT5.")
    return None

def get_ohlc_data(symbol, timeframe, num_bars):
    """
    Get OHLC data from MT5
    """
    # Get current time
    utc_now = datetime.now()

    # Calculate start time
    start_time = utc_now - timedelta(days=num_bars)

    # Get rates directly from MT5
    rates = mt5.copy_rates_from(symbol, timeframe, utc_now, DATA_BUFFER_SIZE)

    if rates is None or len(rates) == 0:
        print(f"Failed to get rates for {symbol}, error code: {mt5.last_error()}")
        return None

    # Convert to DataFrame
    df = pd.DataFrame(rates)

    # Convert time in seconds into the datetime format
    df['time'] = pd.to_datetime(df['time'], unit='s')

    # Select only OHLC columns
    df = df[['time', 'open', 'high', 'low', 'close']]

    # Sort by time
    df = df.sort_values('time')

    print(f"Retrieved {len(df)} bars of data for {symbol}")
    return df

def detect_v_patterns(df, window=5, min_decline_pct=0.05, min_recovery_pct=0.05, spread=1.0):
    """
    Detect V patterns in the data
    """
    patterns = []
    total_potential_patterns = 0

    # Get numpy arrays for faster processing
    times = df['time'].values
    opens = df['open'].values
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values

    # Loop through the data
    for t in range(window, len(df) - 1):
        # Check if current bar is a local minimum
        if lows[t] < lows[t-1] and lows[t] < lows[t+1]:
            total_potential_patterns += 1

            # Find highest high before the potential bottom
            pre_high = max(highs[t-window:t])

            # Calculate decline percentage
            decline_pct = (pre_high - lows[t]) / pre_high * 100

            # Calculate recovery percentage
            post_high = highs[t+1]
            recovery_pct = (post_high - lows[t]) / lows[t] * 100

            # Check if this forms a V pattern
            if decline_pct >= min_decline_pct and recovery_pct >= min_recovery_pct:
                # Calculate entry and exit prices with spread
                entry_price = lows[t] + spread/2  # Buy at ask price
                exit_price = post_high - spread/2  # Sell at bid price

                # Calculate points gained after spread
                points_gained = exit_price - entry_price

                # Skip if points gained is negative (spread makes it unprofitable)
                if points_gained <= 0:
                    continue

                # Calculate additional pattern characteristics for filtering
                bottom_to_high_velocity = post_high - lows[t]
                confirm_range = highs[t+1] - lows[t+1]

                # Create pattern dictionary
                pattern = {
                    'time': times[t],
                    'pre_high': pre_high,
                    'bottom': lows[t],
                    'post_high': post_high,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'points_gained': points_gained,
                    'decline_pct': decline_pct,
                    'recovery_pct': recovery_pct,
                    'bottom_to_high_velocity': bottom_to_high_velocity,
                    'confirm_range': confirm_range
                }

                patterns.append(pattern)

    return patterns, total_potential_patterns

def calculate_kelly_position_size(pattern, current_balance, kelly_fraction=0.25, max_kelly_pct=0.5,
                                 min_volume=0.2, max_volume=50, vol_step=0.01, point_value=1.0):
    """
    Calculate Kelly position size for a pattern
    """
    # Theoretical loss for Kelly calculation (10 points)
    theoretical_loss = 10.0

    # Calculate win rate (100% for our optimized strategy)
    win_rate = 1.0

    # Calculate win/loss ratio
    win_loss_ratio = pattern['points_gained'] / theoretical_loss

    # Calculate Kelly percentage
    kelly_pct = (win_rate * (win_loss_ratio + 1) - 1) / win_loss_ratio

    # Apply Kelly fraction and cap at max_kelly_pct
    fractional_kelly = min(kelly_pct * kelly_fraction, max_kelly_pct)

    # Calculate volume based on Kelly percentage
    kelly_amount = current_balance * fractional_kelly
    risk_amount = theoretical_loss * point_value  # Convert to dollars
    kelly_volume = kelly_amount / risk_amount

    # Ensure volume is within limits and rounded to volume step
    optimal_volume = min(max(min_volume, kelly_volume), max_volume)
    optimal_volume = round(optimal_volume / vol_step) * vol_step

    return optimal_volume

def place_trade(symbol, pattern, volume):
    """
    Place a trade based on the detected pattern
    """
    global patterns_traded, trade_history

    # Get symbol info
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"Failed to get symbol info for {symbol}")
        return False

    # Prepare the trade request
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": mt5.ORDER_TYPE_BUY,
        "price": mt5.symbol_info_tick(symbol).ask,
        "sl": 0.0,  # No stop loss
        "tp": pattern['exit_price'],
        "deviation": 10,
        "magic": 123456,
        "comment": f"V Pattern {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,  # Changed to Fill or Kill as per broker rules
    }

    # Send the trade request
    result = mt5.order_send(request)

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Failed to place trade: {result.retcode}, {result.comment}")
        send_telegram_message(f"❌ Failed to place trade: {result.retcode}, {result.comment}")
        return False

    # Trade placed successfully
    print(f"Trade placed successfully: Ticket #{result.order}")

    # Update counters
    patterns_traded += 1

    # Add to trade history
    trade_info = {
        'ticket': result.order,
        'time': datetime.now(),
        'pattern_time': pattern['time'],
        'volume': volume,
        'entry_price': result.price,
        'exit_price': pattern['exit_price'],
        'points_gained': pattern['points_gained'],
        'profit': pattern['points_gained'] * volume * POINT_VALUE
    }
    trade_history.append(trade_info)

    # Send notification
    send_telegram_message(
        f"🔵 Trade Placed:\n"
        f"Pattern Time: {pattern['time']}\n"
        f"Entry Price: {result.price:.2f}\n"
        f"Take Profit: {pattern['exit_price']:.2f}\n"
        f"Volume: {volume} lots\n"
        f"Expected Profit: ${pattern['points_gained'] * volume * POINT_VALUE:.2f}"
    )

    return True

def check_account_balance():
    """
    Get the current account balance from MT5
    """
    account_info = mt5.account_info()
    if account_info is None:
        print("Failed to get account info")
        return None

    return account_info.balance

def process_new_data(symbol):
    """
    Process new data and look for trading opportunities
    """
    global last_processed_time, patterns_found

    # Get the latest data
    df = get_ohlc_data(symbol, mt5.TIMEFRAME_M1, 1)
    if df is None or len(df) == 0:
        print("Failed to get data")
        return

    # Check if we have new data
    latest_time = df['time'].max()
    if last_processed_time is not None and latest_time <= last_processed_time:
        print(f"No new data since {last_processed_time}")
        return

    # Update last processed time
    last_processed_time = latest_time

    # Detect V patterns
    patterns, potential_patterns = detect_v_patterns(
        df,
        window=LOOKBACK_WINDOW,
        min_decline_pct=MIN_DECLINE_PCT,
        min_recovery_pct=MIN_RECOVERY_PCT,
        spread=SPREAD
    )

    if potential_patterns > 0:
        print(f"Detected {len(patterns)} V patterns out of {potential_patterns} potential patterns")

    # Update patterns found counter
    patterns_found += len(patterns)

    # Filter patterns using optimized trading rules
    filtered_patterns = []
    for pattern in patterns:
        if (pattern['recovery_pct'] >= RECOVERY_PCT_THRESHOLD and
            pattern['bottom_to_high_velocity'] >= VELOCITY_THRESHOLD and
            pattern['confirm_range'] <= RANGE_THRESHOLD):
            filtered_patterns.append(pattern)

    if len(filtered_patterns) > 0:
        print(f"Found {len(filtered_patterns)} patterns that meet trading criteria")

    # Process each filtered pattern
    for pattern in filtered_patterns:
        # Get current account balance
        current_balance = check_account_balance()
        if current_balance is None:
            continue

        # Calculate optimal position size
        volume = calculate_kelly_position_size(
            pattern,
            current_balance,
            kelly_fraction=0.25,
            max_kelly_pct=0.5,
            min_volume=MIN_VOLUME,
            max_volume=MAX_VOLUME,
            vol_step=VOL_STEP,
            point_value=POINT_VALUE
        )

        # Place the trade
        place_trade(symbol, pattern, volume)

def send_daily_summary():
    """
    Send a daily summary of trading activity
    """
    global patterns_found, patterns_traded, trade_history

    # Calculate daily statistics
    total_profit = sum(trade['profit'] for trade in trade_history if (datetime.now() - trade['time']).days < 1)
    avg_profit = total_profit / len(trade_history) if trade_history else 0

    # Get current account balance
    current_balance = check_account_balance()

    # Send summary
    message = (
        f"📊 Daily Trading Summary\n\n"
        f"Patterns Found: {patterns_found}\n"
        f"Patterns Traded: {patterns_traded}\n"
        f"Total Profit: ${total_profit:.2f}\n"
        f"Average Profit per Trade: ${avg_profit:.2f}\n"
        f"Current Account Balance: ${current_balance:.2f}"
    )

    send_telegram_message(message)

    # Reset counters
    patterns_found = 0
    patterns_traded = 0

def daily_summary_thread():
    """
    Thread to send daily summaries
    """
    while True:
        # Get current time
        now = datetime.now()

        # Calculate time until next summary (midnight)
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        seconds_until_midnight = (midnight - now).total_seconds()

        # Sleep until midnight
        time.sleep(seconds_until_midnight)

        # Send summary
        send_daily_summary()

def main():
    """
    Main function
    """
    global SYMBOL, last_processed_time

    print("=== Boom 1000 Index Live Trader ===")
    print("Connecting to MT5...")

    # Set up Telegram bot
    setup_telegram_bot()

    # Connect to MT5
    if not connect_to_mt5(LOGIN, PASSWORD, SERVER):
        print("Failed to connect to MT5. Exiting.")
        return

    # Find Boom 1000 Index symbol
    SYMBOL = find_boom_1000_index_symbol()
    if SYMBOL is None:
        print("Failed to find Boom 1000 Index symbol. Exiting.")
        return

    print(f"Using symbol: {SYMBOL}")
    send_telegram_message(f"🔍 Trading symbol: {SYMBOL}")

    # Start daily summary thread
    summary_thread = Thread(target=daily_summary_thread, daemon=True)
    summary_thread.start()

    # Main trading loop
    print("Starting main trading loop...")
    send_telegram_message("🔄 Starting main trading loop")

    try:
        while True:
            # Process new data
            process_new_data(SYMBOL)

            # Wait for next check
            print(f"Waiting {CHECK_INTERVAL} seconds for next check...")
            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        print("Keyboard interrupt detected. Shutting down...")
        send_telegram_message("⚠️ Trader shutting down due to keyboard interrupt")

    except Exception as e:
        print(f"Error in main loop: {e}")
        send_telegram_message(f"❌ Error in main loop: {e}")

    finally:
        # Shutdown MT5 connection
        mt5.shutdown()
        print("MT5 connection closed")
        send_telegram_message("🔴 Trader stopped. MT5 connection closed")

if __name__ == "__main__":
    main()
