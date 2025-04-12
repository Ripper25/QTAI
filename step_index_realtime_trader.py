import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
import time
import sys
import json
import os
import argparse

# Step Index Trading Parameters
SPREAD = 1.0  # Fixed spread of 1.0 point (confirmed from MT5 terminal)
MIN_VOLUME = 0.1  # Minimum volume of 0.1 lots
MAX_VOLUME = 50  # Maximum volume of 50 lots
VOL_LIMIT = 200  # Volume limit of 200 lots in one direction
VOL_STEP = 0.01  # Volume step of 0.01 lots
POINT_VALUE = 1.0  # $1.00 per point per standard lot (at 0.1 lots, each point is worth $0.10)
INITIAL_BALANCE = 90  # Starting balance of $90

# Pattern detection parameters
LOOKBACK_WINDOW = 5  # Number of bars to look back
MIN_DECLINE_PCT = 0.01  # Minimum percentage decline for V pattern
MIN_RECOVERY_PCT = 0.01  # Minimum percentage recovery for V pattern

# Optimized trading rules (from analysis)
RECOVERY_PCT_THRESHOLD = 0.0248  # Only trade patterns with recovery_pct >= this value
VELOCITY_THRESHOLD = 2.1  # Only trade patterns with bottom_to_high_velocity >= this value
RANGE_THRESHOLD = 2.1  # Only trade patterns with confirm_range <= this value

# Buffer size for real-time data
BUFFER_SIZE = 20  # Number of bars to keep in buffer

# MT5 Connection Parameters
LOGIN = 140276062
PASSWORD = "@Ripper25"
SERVER = "DerivSVG-Server-03"

def connect_to_mt5():
    """
    Connect to the MetaTrader 5 terminal

    Returns:
    - bool: True if connection is successful, False otherwise
    """
    # Check if MT5 is already initialized
    if mt5.terminal_info() is None:
        print("MT5 terminal is not running. Please start the MetaTrader 5 terminal first.")
        print("Attempting to initialize MT5...")

    # Initialize MT5 connection
    if not mt5.initialize():
        print(f"initialize() failed, error code = {mt5.last_error()}")
        print("Please make sure MetaTrader 5 is running and try again.")
        return False

    # Print terminal info
    terminal_info = mt5.terminal_info()
    if terminal_info is not None:
        print(f"Terminal path: {terminal_info.path}")
        print(f"Terminal connected: {terminal_info.connected}")
        print(f"Terminal build: {terminal_info.build}")

    # Connect to the account
    print(f"Attempting to login with account {LOGIN} on server {SERVER}...")
    authorized = mt5.login(LOGIN, PASSWORD, SERVER)
    if not authorized:
        error_code = mt5.last_error()
        print(f"Failed to connect to account {LOGIN}, error code: {error_code}")

        if error_code == -6:
            print("Authorization failed. Please check your login, password, and server name.")
            print("Available servers:")
            servers = mt5.servers_for("deriv")
            if servers is not None and len(servers) > 0:
                for i, srv in enumerate(servers):
                    print(f"{i+1}. {srv.name}")
            else:
                print("No servers found for 'deriv'. Try checking available brokers.")

        mt5.shutdown()
        return False

    print(f"Connected to account {LOGIN} on server {SERVER}")

    # Print account info
    account_info = mt5.account_info()
    if account_info is not None:
        print(f"Account: {account_info.name}")
        print(f"Balance: {account_info.balance}")
        print(f"Equity: {account_info.equity}")

    return True

def find_step_index_symbol():
    """
    Find the correct symbol name for Step Index

    Returns:
    - str: Symbol name or None if not found
    """
    # Get all available symbols
    symbols = mt5.symbols_get()
    print(f"Total symbols available: {len(symbols)}")

    # Common names for Step Index
    possible_names = ["STEP", "Step", "step", "STEPINDEX", "StepIndex", "Step Index"]

    # Try to find an exact match first
    for symbol in symbols:
        if symbol.name in possible_names:
            print(f"Found exact match for Step Index: {symbol.name}")
            return symbol.name

    # Try to find a partial match
    for symbol in symbols:
        for name in possible_names:
            if name in symbol.name:
                print(f"Found potential Step Index symbol: {symbol.name}")
                return symbol.name

    # If no match found, print available symbols
    print("Step Index symbol not found. Here are some available symbols:")
    for i, symbol in enumerate(symbols[:30]):  # Show first 30 symbols
        print(f"{i+1}. {symbol.name}")

    return None

def get_initial_data(symbol, timeframe, num_bars):
    """
    Get initial OHLC data to fill the buffer

    Parameters:
    - symbol (str): Symbol name
    - timeframe: MT5 timeframe (e.g., mt5.TIMEFRAME_M1 for 1-minute)
    - num_bars (int): Number of bars to retrieve

    Returns:
    - list: List of dictionaries with OHLC data
    """
    print(f"Fetching initial {num_bars} bars of OHLC data for {symbol}...")

    # Get the rates
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, num_bars)

    if rates is None or len(rates) == 0:
        print(f"Failed to get initial data for {symbol}, error code: {mt5.last_error()}")
        return []

    # Convert to list of dictionaries
    data_buffer = []
    for rate in rates:
        data_buffer.append({
            'time': datetime.fromtimestamp(rate['time']),
            'open': rate['open'],
            'high': rate['high'],
            'low': rate['low'],
            'close': rate['close']
        })

    print(f"Retrieved {len(data_buffer)} initial data points from {data_buffer[0]['time']} to {data_buffer[-1]['time']}")
    return data_buffer

def get_new_bar(symbol, timeframe):
    """
    Get the latest closed bar

    Parameters:
    - symbol (str): Symbol name
    - timeframe: MT5 timeframe

    Returns:
    - dict: Dictionary with OHLC data or None if no new bar
    """
    # Get the last closed bar
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 1)

    if rates is None or len(rates) == 0:
        print(f"Failed to get latest bar for {symbol}, error code: {mt5.last_error()}")
        return None

    # Convert to dictionary
    bar = {
        'time': datetime.fromtimestamp(rates[0]['time']),
        'open': rates[0]['open'],
        'high': rates[0]['high'],
        'low': rates[0]['low'],
        'close': rates[0]['close']
    }

    return bar

def detect_v_pattern(price_buffer):
    """
    Detect V pattern in the price buffer

    Parameters:
    - price_buffer: List of dictionaries with OHLC data

    Returns:
    - dict: Pattern details if detected, None otherwise
    """
    # Need at least LOOKBACK_WINDOW + 1 bars to detect patterns
    if len(price_buffer) < LOOKBACK_WINDOW + 1:
        return None

    # Check if second-to-last bar is a local minimum
    if (price_buffer[-2]['low'] < price_buffer[-3]['low'] and
        price_buffer[-2]['low'] < price_buffer[-1]['low']):

        # Find highest high before the potential bottom
        pre_high = max(p['high'] for p in price_buffer[:-2])

        # Calculate decline percentage
        decline_pct = (pre_high - price_buffer[-2]['low']) / pre_high * 100

        # Calculate recovery percentage
        recovery_pct = (price_buffer[-1]['high'] - price_buffer[-2]['low']) / price_buffer[-2]['low'] * 100

        # Check if this forms a V pattern
        if decline_pct >= MIN_DECLINE_PCT and recovery_pct >= MIN_RECOVERY_PCT:
            # Calculate entry and exit prices with spread
            entry_price = price_buffer[-2]['low'] + SPREAD/2  # Buy at ask price
            exit_price = price_buffer[-1]['high'] - SPREAD/2  # Sell at bid price

            # Calculate points gained after spread
            points_gained = exit_price - entry_price

            # Calculate additional pattern characteristics for filtering
            bottom_to_high_velocity = price_buffer[-1]['high'] - price_buffer[-2]['low']
            confirm_range = price_buffer[-1]['high'] - price_buffer[-1]['low']

            # Apply optimized trading rules
            if (recovery_pct >= RECOVERY_PCT_THRESHOLD and
                bottom_to_high_velocity >= VELOCITY_THRESHOLD and
                confirm_range <= RANGE_THRESHOLD):

                # This pattern passes our optimized rules
                return {
                    'type': 'V',
                    'bottom_time': price_buffer[-2]['time'],
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'points_gained': points_gained,
                    'profit_per_lot': points_gained * (1/POINT_VALUE * 10),
                    'decline_pct': decline_pct,
                    'recovery_pct': recovery_pct,
                    'bottom_to_high_velocity': bottom_to_high_velocity,
                    'confirm_range': confirm_range
                }
            else:
                # Pattern filtered out by our rules
                print(f"V pattern filtered out at {price_buffer[-2]['time']} (recovery_pct: {recovery_pct:.4f}%, velocity: {bottom_to_high_velocity:.4f}, range: {confirm_range:.4f})")
                return None

    return None

def calculate_position_size(current_balance, pattern, trade_history):
    """
    Calculate position size using Kelly Criterion

    Parameters:
    - current_balance: Current account balance
    - pattern: Pattern details
    - trade_history: List of previous trades

    Returns:
    - float: Optimal position size in lots
    """
    # Theoretical loss for Kelly calculation (10 points)
    theoretical_loss = 10.0

    # Calculate win rate from historical data
    total_trades = len(trade_history)
    winning_trades = sum(1 for trade in trade_history if trade['points_gained'] > 0)

    if total_trades >= 5:
        win_rate = winning_trades / total_trades
    else:
        win_rate = 0.8  # Conservative estimate for first few trades

    # Calculate average win amount from historical data
    if winning_trades > 0:
        total_profit_points = sum(trade['points_gained'] for trade in trade_history if trade['points_gained'] > 0)
        avg_win = total_profit_points / winning_trades
    else:
        avg_win = pattern['points_gained']

    # Calculate win/loss ratio
    win_loss_ratio = avg_win / theoretical_loss

    # Calculate Kelly percentage
    kelly_pct = (win_rate * (win_loss_ratio + 1) - 1) / win_loss_ratio if win_loss_ratio > 0 else 0

    # Apply Kelly fraction (1/4 Kelly) and cap at 50%
    fractional_kelly = min(kelly_pct * 0.25, 0.5)

    # Calculate volume based on Kelly percentage
    kelly_amount = current_balance * fractional_kelly
    risk_amount = theoretical_loss * (1/POINT_VALUE * 10)  # Convert to dollars
    kelly_volume = kelly_amount / risk_amount if risk_amount > 0 else MIN_VOLUME

    # Ensure volume is within limits and rounded to volume step
    optimal_volume = min(max(MIN_VOLUME, kelly_volume), MAX_VOLUME)
    optimal_volume = round(optimal_volume / VOL_STEP) * VOL_STEP

    return optimal_volume

def validate_data_continuity(data_buffer):
    """
    Check for gaps in the data buffer

    Parameters:
    - data_buffer: List of dictionaries with OHLC data

    Returns:
    - bool: True if data is continuous, False if gaps detected
    - list: List of gaps detected (empty if no gaps)
    """
    gaps = []

    for i in range(1, len(data_buffer)):
        time_diff = (data_buffer[i]['time'] - data_buffer[i-1]['time']).total_seconds()
        # For 1-minute data, expect 60 seconds between bars
        if time_diff > 70:  # Allow some flexibility (70 seconds instead of 60)
            gap = {
                'start_time': data_buffer[i-1]['time'],
                'end_time': data_buffer[i]['time'],
                'gap_seconds': time_diff
            }
            gaps.append(gap)
            print(f"WARNING: Data gap detected between {gap['start_time']} and {gap['end_time']} ({gap['gap_seconds']} seconds)")

    return len(gaps) == 0, gaps

def ensure_mt5_connection():
    """
    Ensure MT5 is connected, reconnect if necessary

    Returns:
    - bool: True if connected, False otherwise
    """
    if not mt5.terminal_info() or not mt5.terminal_info().connected:
        print("MT5 connection lost. Attempting to reconnect...")
        mt5.shutdown()
        time.sleep(5)
        if not connect_to_mt5():
            print("Failed to reconnect to MT5.")
            return False
        print("Successfully reconnected to MT5.")
    return True

def recover_from_data_gap(symbol, last_known_time):
    """
    Recover missing data after a gap

    Parameters:
    - symbol: Symbol name
    - last_known_time: Datetime of the last known bar

    Returns:
    - list: List of recovered bars (empty if recovery failed)
    """
    current_time = datetime.now()
    minutes_gap = int((current_time - last_known_time).total_seconds() / 60) + 1

    print(f"Attempting to recover {minutes_gap} minutes of missing data...")

    # Get missing bars
    missing_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, minutes_gap)

    if missing_rates is None or len(missing_rates) == 0:
        print("Failed to recover missing data.")
        return []

    # Convert to list of dictionaries
    recovered_data = []
    for rate in missing_rates:
        bar_time = datetime.fromtimestamp(rate['time'])
        if bar_time > last_known_time:
            recovered_data.append({
                'time': bar_time,
                'open': rate['open'],
                'high': rate['high'],
                'low': rate['low'],
                'close': rate['close']
            })

    print(f"Recovered {len(recovered_data)} bars of missing data.")
    return recovered_data

def check_heartbeat(last_heartbeat):
    """
    Check if the system is still functioning properly

    Parameters:
    - last_heartbeat: Datetime of the last heartbeat

    Returns:
    - bool: True if heartbeat is recent, False otherwise
    """
    current_time = datetime.now()
    if (current_time - last_heartbeat).total_seconds() > 300:  # 5 minutes
        print("WARNING: No heartbeat for 5 minutes. Checking system...")
        return False
    return True

def save_trading_state(data_buffer, trade_history, current_balance, last_bar_time):
    """
    Save the current state of the trading system

    Parameters:
    - data_buffer: List of dictionaries with OHLC data
    - trade_history: List of executed trades
    - current_balance: Current account balance
    - last_bar_time: Datetime of the last processed bar
    """
    # Convert datetime objects to strings for JSON serialization
    serializable_buffer = []
    for bar in data_buffer:
        serializable_bar = bar.copy()
        serializable_bar['time'] = bar['time'].isoformat()
        serializable_buffer.append(serializable_bar)

    serializable_trades = []
    for trade in trade_history:
        serializable_trade = trade.copy()
        serializable_trade['time'] = trade['time'].isoformat()
        serializable_trades.append(serializable_trade)

    state = {
        'timestamp': datetime.now().isoformat(),
        'data_buffer': serializable_buffer,
        'trade_history': serializable_trades,
        'current_balance': current_balance,
        'last_bar_time': last_bar_time.isoformat()
    }

    with open('trading_state.json', 'w') as f:
        json.dump(state, f, indent=2)

    print(f"Trading state saved at {datetime.now()}")

def load_trading_state():
    """
    Load the saved trading state

    Returns:
    - dict: Loaded state or None if loading failed
    """
    try:
        with open('trading_state.json', 'r') as f:
            state = json.load(f)

        # Convert string timestamps back to datetime
        for bar in state['data_buffer']:
            bar['time'] = datetime.fromisoformat(bar['time'])

        for trade in state['trade_history']:
            trade['time'] = datetime.fromisoformat(trade['time'])

        state['last_bar_time'] = datetime.fromisoformat(state['last_bar_time'])

        print(f"Trading state loaded from {state['timestamp']}")
        return state
    except FileNotFoundError:
        print("No saved state found. Starting fresh.")
        return None
    except Exception as e:
        print(f"Error loading saved state: {e}")
        return None

def check_open_positions(symbol):
    """
    Check if there are any open positions for the given symbol

    Parameters:
    - symbol: Symbol name

    Returns:
    - bool: True if there are open positions, False otherwise
    """
    positions = mt5.positions_get(symbol=symbol)
    if positions is None:
        print(f"No positions found for {symbol}, error code: {mt5.last_error()}")
        return False

    return len(positions) > 0

def execute_trade(symbol, pattern, volume):
    """
    Execute a trade based on the detected pattern

    Parameters:
    - symbol: Symbol name
    - pattern: Pattern details
    - volume: Position size in lots

    Returns:
    - bool: True if trade executed successfully, False otherwise
    """
    # Check if there are already open positions for this symbol
    if check_open_positions(symbol):
        print(f"WARNING: There are already open positions for {symbol}. Skipping this trade.")
        return False

    print(f"Executing trade for {symbol} at {pattern['bottom_time']}:")
    print(f"  Entry Price: {pattern['entry_price']}")
    print(f"  Exit Price: {pattern['exit_price']}")
    print(f"  Volume: {volume} lots")
    print(f"  Points Gained: {pattern['points_gained']}")
    print(f"  Profit: ${pattern['points_gained'] * volume * POINT_VALUE:.2f}")

    # Place a real trade using MT5 API
    # Define trade request
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": mt5.ORDER_TYPE_BUY,
        "price": pattern['entry_price'],
        "sl": 0.0,  # No stop loss
        "tp": pattern['exit_price'],  # Take profit at exit price
        "deviation": 10,
        "magic": 123456,
        "comment": "QUANTA V Pattern",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    # Send trade request
    result = mt5.order_send(request)
    if result is None:
        print(f"Trade execution failed, error code: {mt5.last_error()}")
        return False

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Trade execution failed, error code: {result.retcode}")
        return False

    print(f"Trade executed successfully, ticket: {result.order}")

    return True

def run_realtime_trader():
    """
    Main function to run the real-time trader
    """
    print("=== QUANTA Step Index Real-Time Trader ===")
    print("Connecting to MT5...")

    # Connect to MT5
    if not connect_to_mt5():
        print("Failed to connect to MT5. Exiting.")
        return

    # Find Step Index symbol
    symbol = find_step_index_symbol()
    if symbol is None:
        print("Could not find Step Index symbol. Please check the symbol name in MT5.")

        # Ask user to input the symbol manually
        user_symbol = input("Please enter the exact symbol name for Step Index as shown in MT5: ")
        if user_symbol:
            symbol = user_symbol
        else:
            mt5.shutdown()
            return

    print(f"Using symbol: {symbol}")

    # Try to load saved state
    saved_state = load_trading_state()
    if saved_state:
        # Restore from saved state
        data_buffer = saved_state['data_buffer']
        trade_history = saved_state['trade_history']
        current_balance = saved_state['current_balance']
        last_bar_time = saved_state['last_bar_time']
        print("Restored trading state from previous session.")
    else:
        # Get initial data to fill the buffer
        data_buffer = get_initial_data(symbol, mt5.TIMEFRAME_M1, BUFFER_SIZE)
        if not data_buffer:
            print("Failed to get initial data. Exiting.")
            mt5.shutdown()
            return

        # Get actual account balance from MT5
        account_info = mt5.account_info()
        if account_info is not None:
            current_balance = account_info.balance
            print(f"Using actual account balance: ${current_balance:.2f}")
        else:
            # Fallback to initial balance if account info is not available
            current_balance = INITIAL_BALANCE
            print(f"Could not get actual account balance. Using default: ${current_balance:.2f}")

        trade_history = []
        last_bar_time = data_buffer[-1]['time']

    # Initialize heartbeat and failure tracking
    last_heartbeat = datetime.now()
    consecutive_failures = 0
    max_failures = 5
    state_save_interval = 300  # Save state every 5 minutes
    last_state_save = datetime.now()

    print("\nStarting real-time trading...")
    print(f"Initial balance: ${current_balance:.2f}")
    print(f"Buffer size: {len(data_buffer)} bars")
    print(f"Last bar time: {last_bar_time}")
    print("\nWaiting for new bars...")

    try:
        while True:
            # Check heartbeat and connection
            if not check_heartbeat(last_heartbeat):
                print("Heartbeat check failed. Attempting recovery...")
                if not ensure_mt5_connection():
                    raise Exception("Failed to recover connection after heartbeat failure.")
                last_heartbeat = datetime.now()

            # Periodically save state
            if (datetime.now() - last_state_save).total_seconds() > state_save_interval:
                save_trading_state(data_buffer, trade_history, current_balance, last_bar_time)
                last_state_save = datetime.now()

            # Get the latest bar
            new_bar = get_new_bar(symbol, mt5.TIMEFRAME_M1)

            if new_bar is None:
                consecutive_failures += 1
                print(f"Failed to get latest bar. Attempt {consecutive_failures}/{max_failures}")

                if consecutive_failures >= max_failures:
                    print("Maximum consecutive failures reached. Attempting recovery...")
                    if ensure_mt5_connection():
                        # Try to recover missing data
                        recovered_data = recover_from_data_gap(symbol, last_bar_time)
                        if recovered_data:
                            # Process recovered data
                            for bar in recovered_data:
                                print(f"Processing recovered bar: {bar['time']}")
                                data_buffer.append(bar)
                                if len(data_buffer) > BUFFER_SIZE:
                                    data_buffer.pop(0)

                                # Detect patterns for each recovered bar
                                pattern = detect_v_pattern(data_buffer)
                                if pattern:
                                    print(f"V pattern detected in recovered data at {pattern['bottom_time']}: {pattern['points_gained']:.2f} points")

                                    # Calculate position size
                                    volume = calculate_position_size(current_balance, pattern, trade_history)

                                    # Execute trade
                                    if execute_trade(symbol, pattern, volume):
                                        # Calculate profit
                                        profit = pattern['points_gained'] * volume * POINT_VALUE

                                        # Update balance
                                        current_balance += profit

                                        # Add to trade history
                                        trade = {
                                            'time': pattern['bottom_time'],
                                            'entry_price': pattern['entry_price'],
                                            'exit_price': pattern['exit_price'],
                                            'volume': volume,
                                            'points_gained': pattern['points_gained'],
                                            'profit': profit,
                                            'balance_before': current_balance - profit,
                                            'balance_after': current_balance
                                        }
                                        trade_history.append(trade)
                                        print(f"Trade executed successfully. New balance: ${current_balance:.2f}")

                                last_bar_time = bar['time']

                            consecutive_failures = 0
                            print("Recovery successful. Continuing normal operation.")
                        else:
                            print("Could not recover data. Will continue trying.")
                    else:
                        print("Could not reconnect to MT5. Will continue trying.")

                time.sleep(30)  # Wait longer when there are failures
                continue

            # Reset failure counter on success
            consecutive_failures = 0
            last_heartbeat = datetime.now()

            # Check if this is a new bar
            if new_bar['time'] > last_bar_time:
                # Check for data gaps
                expected_time = last_bar_time + timedelta(minutes=1)
                if new_bar['time'] > expected_time:
                    print(f"Data gap detected. Expected: {expected_time}, Received: {new_bar['time']}")
                    # Try to recover missing data
                    gap_start = last_bar_time + timedelta(minutes=1)
                    gap_end = new_bar['time'] - timedelta(minutes=1)
                    gap_minutes = int((gap_end - gap_start).total_seconds() / 60) + 1

                    if gap_minutes > 0:
                        print(f"Attempting to recover {gap_minutes} minutes of missing data...")
                        # Get missing bars
                        from_time = int(gap_start.timestamp())
                        to_time = int(gap_end.timestamp())
                        missing_rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, from_time, to_time)

                        if missing_rates is not None and len(missing_rates) > 0:
                            # Process missing bars
                            for rate in missing_rates:
                                missing_bar = {
                                    'time': datetime.fromtimestamp(rate['time']),
                                    'open': rate['open'],
                                    'high': rate['high'],
                                    'low': rate['low'],
                                    'close': rate['close']
                                }
                                print(f"Processing gap bar: {missing_bar['time']}")
                                data_buffer.append(missing_bar)
                                if len(data_buffer) > BUFFER_SIZE:
                                    data_buffer.pop(0)

                                # Process pattern for missing bar
                                pattern = detect_v_pattern(data_buffer)
                                if pattern:
                                    print(f"V pattern detected in gap data at {pattern['bottom_time']}: {pattern['points_gained']:.2f} points")

                                    # Calculate position size
                                    volume = calculate_position_size(current_balance, pattern, trade_history)

                                    # Execute trade
                                    if execute_trade(symbol, pattern, volume):
                                        # Calculate profit
                                        profit = pattern['points_gained'] * volume * POINT_VALUE

                                        # Update balance
                                        current_balance += profit

                                        # Add to trade history
                                        trade = {
                                            'time': pattern['bottom_time'],
                                            'entry_price': pattern['entry_price'],
                                            'exit_price': pattern['exit_price'],
                                            'volume': volume,
                                            'points_gained': pattern['points_gained'],
                                            'profit': profit,
                                            'balance_before': current_balance - profit,
                                            'balance_after': current_balance
                                        }
                                        trade_history.append(trade)
                                        print(f"Trade executed successfully. New balance: ${current_balance:.2f}")

                                last_bar_time = missing_bar['time']

                            print(f"Recovered and processed {len(missing_rates)} missing bars.")

                # Process the new bar normally
                print(f"\nNew bar received: {new_bar['time']}")

                # Update the buffer
                data_buffer.append(new_bar)
                if len(data_buffer) > BUFFER_SIZE:
                    data_buffer.pop(0)

                # Update last bar time
                last_bar_time = new_bar['time']

                # Check data continuity
                is_continuous, gaps = validate_data_continuity(data_buffer)
                if not is_continuous:
                    print(f"WARNING: Data buffer contains {len(gaps)} gaps. This may affect pattern detection.")

                # Detect patterns
                pattern = detect_v_pattern(data_buffer)

                if pattern:
                    print(f"V pattern detected at {pattern['bottom_time']}: {pattern['points_gained']:.2f} points")

                    # Calculate position size
                    volume = calculate_position_size(current_balance, pattern, trade_history)

                    # Execute trade
                    if execute_trade(symbol, pattern, volume):
                        # Calculate profit
                        profit = pattern['points_gained'] * volume * POINT_VALUE

                        # Update balance
                        current_balance += profit

                        # Add to trade history
                        trade = {
                            'time': pattern['bottom_time'],
                            'entry_price': pattern['entry_price'],
                            'exit_price': pattern['exit_price'],
                            'volume': volume,
                            'points_gained': pattern['points_gained'],
                            'profit': profit,
                            'balance_before': current_balance - profit,
                            'balance_after': current_balance
                        }
                        trade_history.append(trade)

                        print(f"Trade executed successfully. New balance: ${current_balance:.2f}")

                        # Print trade summary
                        print("\nTrade Summary:")
                        print(f"Time: {trade['time']}")
                        print(f"Entry: {trade['entry_price']}")
                        print(f"Exit: {trade['exit_price']}")
                        print(f"Volume: {trade['volume']}")
                        print(f"Points: {trade['points_gained']}")
                        print(f"Profit: ${trade['profit']:.2f}")
                        print(f"Balance: ${trade['balance_after']:.2f}")
                        print(f"Total Trades: {len(trade_history)}")
                        # Get the starting balance (either from saved state or actual account balance)
                        if saved_state:
                            starting_balance = saved_state['current_balance']
                        else:
                            # Use the account balance we got earlier
                            starting_balance = account_info.balance if account_info is not None else INITIAL_BALANCE

                        print(f"Total Profit: ${current_balance - starting_balance:.2f}")

                        # Calculate ROI (handle case where starting balance is 0)
                        if starting_balance > 0:
                            roi = ((current_balance - starting_balance) / starting_balance) * 100
                            print(f"ROI: {roi:.2f}%")
                        else:
                            print("ROI: N/A (starting balance was 0)")

            # Wait for the next bar (check every 10 seconds)
            time.sleep(10)

    except KeyboardInterrupt:
        print("\nTrading stopped by user.")
        # Save state on exit
        save_trading_state(data_buffer, trade_history, current_balance, last_bar_time)
    except Exception as e:
        print(f"\nError occurred: {e}")
        # Log the error
        with open("error_log.txt", "a") as f:
            f.write(f"{datetime.now()}: {str(e)}\n")
        # Save state on error
        save_trading_state(data_buffer, trade_history, current_balance, last_bar_time)
    finally:
        # Print final summary
        print("\n=== Trading Session Summary ===")

        # Get the starting balance (either from saved state or initial balance)
        if saved_state:
            starting_balance = saved_state['current_balance']
        else:
            # Try to get account info again
            account_info = mt5.account_info()
            starting_balance = account_info.balance if account_info is not None else INITIAL_BALANCE

        print(f"Starting Balance: ${starting_balance:.2f}")
        print(f"Final Balance: ${current_balance:.2f}")
        print(f"Total Profit: ${current_balance - starting_balance:.2f}")
        # Calculate ROI (handle case where starting balance is 0)
        if starting_balance > 0:
            roi = ((current_balance - starting_balance) / starting_balance) * 100
            print(f"Return on Investment: {roi:.2f}%")
        else:
            print("Return on Investment: N/A (starting balance was 0)")
        print(f"Total Trades: {len(trade_history)}")

        if trade_history:
            winning_trades = sum(1 for trade in trade_history if trade['points_gained'] > 0)
            win_rate = winning_trades / len(trade_history) * 100
            print(f"Win Rate: {win_rate:.2f}%")

            # Print last 5 trades
            print("\nLast 5 Trades:")
            for trade in trade_history[-5:]:
                print(f"Time: {trade['time']} | Points: {trade['points_gained']:.2f} | Profit: ${trade['profit']:.2f}")

        # Shutdown MT5 connection
        mt5.shutdown()
        print("\nMT5 connection closed.")

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='QUANTA Step Index Real-Time Trader')
    parser.add_argument('--mode', type=str, default='live', choices=['live', 'backtest'],
                        help='Trading mode: live or backtest (default: live)')
    args = parser.parse_args()

    # Ensure we're in live mode
    if args.mode != 'live':
        print(f"WARNING: Requested mode '{args.mode}' is not supported. Forcing 'live' mode.")

    print(f"Running in LIVE mode with real account balance")
    run_realtime_trader()
