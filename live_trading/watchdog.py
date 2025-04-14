import subprocess
import time
import os
import sys
import signal
import psutil
from datetime import datetime, timedelta
import telegram

# Watchdog Parameters
CHECK_INTERVAL = 60  # Check every 60 seconds
MAX_RESTART_ATTEMPTS = 5  # Maximum number of restart attempts
RESTART_COOLDOWN = 300  # Cooldown period between restart attempts (5 minutes)
MAINTENANCE_HOURS = [1, 2]  # MT5 server maintenance hours (UTC)

# Telegram Bot Parameters
TELEGRAM_TOKEN = "7717225420:AAE5TNborRsbniBfuGc4yuPQnftSZ2Gyuvs"  # @live_vmbot
TELEGRAM_CHAT_ID = 1435296772

# Global variables
bot = None
trader_process = None
restart_attempts = 0
last_restart_time = None

def setup_telegram_bot():
    """
    Set up the Telegram bot for sending notifications
    """
    global bot
    try:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        print("Telegram bot initialized successfully")
        send_telegram_message("🔍 Watchdog started")
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

def is_maintenance_time():
    """
    Check if it's MT5 server maintenance time
    """
    current_hour = datetime.utcnow().hour
    return current_hour in MAINTENANCE_HOURS

def start_trader():
    """
    Start the live trader process
    """
    global trader_process
    
    # Get the path to the trader script
    trader_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "boom_1000_live_trader.py")
    
    # Check if the script exists
    if not os.path.exists(trader_script):
        print(f"Trader script not found: {trader_script}")
        send_telegram_message(f"❌ Trader script not found: {trader_script}")
        return False
    
    # Start the trader process
    try:
        trader_process = subprocess.Popen([sys.executable, trader_script])
        print(f"Started trader process with PID {trader_process.pid}")
        send_telegram_message(f"🚀 Started trader process with PID {trader_process.pid}")
        return True
    except Exception as e:
        print(f"Error starting trader process: {e}")
        send_telegram_message(f"❌ Error starting trader process: {e}")
        return False

def check_trader_process():
    """
    Check if the trader process is still running
    """
    global trader_process
    
    if trader_process is None:
        return False
    
    # Check if the process is still running
    if trader_process.poll() is None:
        # Process is still running
        return True
    else:
        # Process has exited
        exit_code = trader_process.returncode
        print(f"Trader process exited with code {exit_code}")
        send_telegram_message(f"⚠️ Trader process exited with code {exit_code}")
        trader_process = None
        return False

def restart_trader():
    """
    Restart the trader process
    """
    global restart_attempts, last_restart_time
    
    # Check if we've exceeded the maximum number of restart attempts
    if restart_attempts >= MAX_RESTART_ATTEMPTS:
        # Check if we're in the cooldown period
        if last_restart_time is not None and (datetime.now() - last_restart_time).total_seconds() < RESTART_COOLDOWN:
            print(f"Maximum restart attempts reached. Waiting for cooldown period to expire.")
            send_telegram_message(f"⚠️ Maximum restart attempts reached. Waiting for cooldown period to expire.")
            return False
        else:
            # Reset restart attempts after cooldown period
            restart_attempts = 0
    
    # Increment restart attempts
    restart_attempts += 1
    last_restart_time = datetime.now()
    
    # Kill the trader process if it's still running
    if trader_process is not None and trader_process.poll() is None:
        try:
            # Try to terminate gracefully first
            trader_process.terminate()
            
            # Wait for process to terminate
            try:
                trader_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Force kill if it doesn't terminate
                trader_process.kill()
        except Exception as e:
            print(f"Error terminating trader process: {e}")
    
    # Start the trader process
    return start_trader()

def kill_all_python_processes():
    """
    Kill all Python processes except the current one
    """
    current_pid = os.getpid()
    
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            # Check if it's a Python process
            if 'python' in proc.info['name'].lower() and proc.info['pid'] != current_pid:
                print(f"Killing Python process with PID {proc.info['pid']}")
                psutil.Process(proc.info['pid']).kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

def main():
    """
    Main function
    """
    print("=== Boom 1000 Index Trader Watchdog ===")
    
    # Set up Telegram bot
    setup_telegram_bot()
    
    # Kill any existing Python processes
    kill_all_python_processes()
    
    # Start the trader process
    start_trader()
    
    # Main watchdog loop
    print("Starting main watchdog loop...")
    
    try:
        while True:
            # Check if it's maintenance time
            if is_maintenance_time():
                print("MT5 server maintenance time. Waiting...")
                send_telegram_message("⚙️ MT5 server maintenance time. Waiting...")
                
                # Wait until maintenance is over
                while is_maintenance_time():
                    time.sleep(60)
                
                # Restart trader after maintenance
                print("Maintenance period over. Restarting trader...")
                send_telegram_message("🔄 Maintenance period over. Restarting trader...")
                restart_trader()
            
            # Check if the trader process is still running
            if not check_trader_process():
                print("Trader process not running. Restarting...")
                restart_trader()
            
            # Wait for next check
            time.sleep(CHECK_INTERVAL)
    
    except KeyboardInterrupt:
        print("Keyboard interrupt detected. Shutting down...")
        send_telegram_message("⚠️ Watchdog shutting down due to keyboard interrupt")
        
        # Kill the trader process
        if trader_process is not None and trader_process.poll() is None:
            trader_process.terminate()
    
    except Exception as e:
        print(f"Error in main loop: {e}")
        send_telegram_message(f"❌ Error in main loop: {e}")

if __name__ == "__main__":
    main()
