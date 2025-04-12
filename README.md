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

## Files

- `step_index_realtime_trader.py` - Main trading script
- `watchdog.py` - Monitoring script for automatic recovery

## Usage

1. Ensure MT5 is installed and running
2. Run the watchdog script: `python watchdog.py`
3. The system will automatically trade when valid patterns are detected
