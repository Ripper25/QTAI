# Boom 1000 Index Live Trading System

This system implements the exact same trading strategy as the backtest, connecting directly to the MT5 terminal to retrieve real-time data and execute trades.

## Components

1. **boom_1000_live_trader.py**: The main trading script that connects to MT5, retrieves real-time data, detects patterns, and executes trades.
2. **watchdog.py**: A monitoring script that ensures the trader is always running, restarting it if it crashes.

## Features

- **Direct MT5 Connection**: Connects directly to the MT5 terminal without any fallbacks.
- **Real-Time Pattern Detection**: Detects V patterns in real-time as they form.
- **Kelly Criterion Position Sizing**: Uses the same Kelly Criterion position sizing as the backtest.
- **Telegram Notifications**: Sends notifications for trade executions and daily summaries.
- **Automatic Recovery**: The watchdog monitors the trader and restarts it if it crashes.
- **Maintenance Period Handling**: Automatically handles MT5 server maintenance periods.

## Trading Parameters

The live trader uses the exact same "golden parameters" as the backtest:

- **LOOKBACK_WINDOW = 5**: 5-bar window for detecting local minimums
- **MIN_DECLINE_PCT = 0.01**: Minimum 0.01% decline to form a V pattern
- **MIN_RECOVERY_PCT = 0.01**: Minimum 0.01% recovery to form a V pattern
- **RECOVERY_PCT_THRESHOLD = 0.0248**: Minimum percentage recovery for trading
- **VELOCITY_THRESHOLD = 2.1**: Minimum bottom-to-high velocity for trading
- **RANGE_THRESHOLD = 2.1**: Maximum confirmation range for trading

## Trading Rules

1. **Pattern Detection**: The script detects V patterns in real-time by identifying local minimums.
2. **Pattern Filtering**: Only patterns that meet the optimized filtering criteria are traded.
3. **Entry**: Entry occurs at the current ask price when a valid pattern is detected.
4. **Exit**: A take profit order is placed at the high of the confirmation bar minus half the spread.
5. **Position Sizing**: The Kelly Criterion is used to calculate the optimal position size based on the current account balance.
6. **Order Execution**: Uses Fill or Kill (FOK) order execution as per broker rules - orders must be filled completely at the specified price or not at all.

## Requirements

- Python 3.7 or higher
- MetaTrader 5 terminal installed and running
- Python packages: pandas, numpy, MetaTrader5, telegram-python-bot, psutil

## Installation

1. Install the required Python packages:
   ```
   pip install pandas numpy MetaTrader5 python-telegram-bot psutil
   ```

2. Ensure the MT5 terminal is installed and running.

3. Update the login credentials in the scripts if needed.

## Usage

1. Start the watchdog, which will automatically start the trader:
   ```
   python watchdog.py
   ```

2. The watchdog will monitor the trader and restart it if it crashes.

3. You will receive Telegram notifications for trade executions and daily summaries.

## Monitoring

- **Telegram Notifications**: The system sends notifications to the specified Telegram chat for trade executions and daily summaries.
- **Console Output**: Both the trader and watchdog print detailed logs to the console.

## Important Notes

1. **No Fallbacks**: The system connects directly to the MT5 terminal without any fallbacks. If the MT5 terminal is not running or the connection fails, the system will not work.

2. **Real Account**: The system is configured to use a real account. Make sure you understand the risks before running it.

3. **Maintenance Periods**: The system automatically handles MT5 server maintenance periods, waiting until maintenance is over before restarting the trader.

4. **No Simulations**: The system uses only the actual MT5 account balance and does not reference any initial balance constant.

5. **Kelly Criterion**: The system uses the Kelly Criterion for position sizing, which can be aggressive. The implementation uses a fractional Kelly (25%) to reduce risk.

## Troubleshooting

If you encounter any issues:

1. Check that the MT5 terminal is running and connected to the server.
2. Verify that the login credentials are correct.
3. Check the console output for error messages.
4. Restart the watchdog if needed.

## Disclaimer

Trading involves risk. This system is provided as-is with no guarantees. Use at your own risk.
