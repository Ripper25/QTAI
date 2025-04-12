import subprocess
import time
import os
import datetime

def monitor_trading_script():
    """
    Monitor the trading script and restart it if it crashes
    """
    print("=== QUANTA (PROP-FIRM) Watchdog ===")
    print(f"Started at: {datetime.datetime.now()}")
    print("Monitoring step_index_realtime_trader.py...")
    
    restart_count = 0
    max_restarts = 10  # Maximum number of restarts per day
    restart_interval = 60  # Wait 60 seconds before restarting
    
    # Create logs directory if it doesn't exist
    if not os.path.exists("logs"):
        os.makedirs("logs")
    
    while True:
        # Generate log filename with timestamp
        log_filename = f"logs/trading_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        print(f"\nStarting trading script (attempt {restart_count + 1})...")
        print(f"Log file: {log_filename}")
        
        # Open log file
        with open(log_filename, "w") as log_file:
            # Start the trading script and redirect output to log file
            process = subprocess.Popen(
                ["python", "step_index_realtime_trader.py"],
                stdout=log_file,
                stderr=log_file
            )
            
            # Wait for the process to complete
            start_time = datetime.datetime.now()
            process.wait()
            end_time = datetime.datetime.now()
            
            # Calculate runtime
            runtime = end_time - start_time
            
            # Log the exit
            log_file.write(f"\n\nProcess exited with code {process.returncode} at {end_time}\n")
            log_file.write(f"Runtime: {runtime}\n")
        
        # Check if we should restart
        restart_count += 1
        if restart_count >= max_restarts:
            print(f"Maximum restart count ({max_restarts}) reached. Exiting watchdog.")
            break
        
        print(f"Trading script exited with code {process.returncode} after running for {runtime}")
        print(f"Waiting {restart_interval} seconds before restarting...")
        time.sleep(restart_interval)
        
        # Reset restart count at midnight
        current_time = datetime.datetime.now()
        if current_time.hour == 0 and current_time.minute < 5:  # Reset around midnight
            print("Resetting restart counter at midnight")
            restart_count = 0

if __name__ == "__main__":
    try:
        monitor_trading_script()
    except KeyboardInterrupt:
        print("\nWatchdog stopped by user.")
    except Exception as e:
        print(f"\nWatchdog error: {e}")
