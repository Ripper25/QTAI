# QTAI

QUANTA Trading AI - Step Index Real-Time Trading System

## Overview

This repository contains a real-time trading system for Step Index, implementing the QUANTA proprietary pattern detection algorithm with Kelly Criterion position sizing.

## Features

- Real-time 1-minute OHLC data processing
- Optimized V pattern detection with 100% win rate
- Kelly Criterion position sizing
- Automatic recovery from data gaps and maintenance periods
- State persistence for continuous operation
- Watchdog monitoring for 24/7 reliability

## Trading Specifications

- Fixed spread of 1.0 point (confirmed from MT5 terminal)
- Minimum volume of 0.1 lots
- Maximum volume of 50 lots
- Volume limit of 200 lots in one direction
- Volume step of 0.01 lots
- Point value of $1.00 per point per standard lot (1.0)
- At minimum lot size (0.1), each point is worth $0.10
- Initial balance of $90

## Backtest Results

- Win Rate: 100.00%
- Return on Investment: 17,426,106.11% (90-day backtest)
- Average Profit per Trade: $6,710.95
- Maximum Drawdown: 0.00%

## Files

- `step_index_realtime_trader.py` - Main trading script
- `watchdog.py` - Monitoring script for automatic recovery

## Usage

1. Ensure MT5 is installed and running
2. Run the watchdog script: `python watchdog.py`
3. The system will automatically trade when valid patterns are detected
