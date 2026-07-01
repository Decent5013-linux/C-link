#!/bin/bash

# Script to run cpm.py and restart it if it crashes, stops, or runs longer than 2 minutes

SCRIPT="click.py"
LOG_FILE="cpm_monitor.log"
RESTART_DELAY=5  # seconds to wait before restarting
TIMEOUT=120      # 2 minutes in seconds

echo "$(date): Starting monitor for $SCRIPT with ${TIMEOUT}s timeout" >> "$LOG_FILE"

while true; do
    echo "$(date): Starting $SCRIPT" >> "$LOG_FILE"
    
    # Run the Python script in the background
    python "$SCRIPT" &
    PYTHON_PID=$!
    
    # Wait for the script to finish or timeout
    SECONDS_ELAPSED=0
    while kill -0 $PYTHON_PID 2>/dev/null; do
        sleep 1
        SECONDS_ELAPSED=$((SECONDS_ELAPSED + 1))
        
        if [ $SECONDS_ELAPSED -ge $TIMEOUT ]; then
            echo "$(date): $SCRIPT running for ${SECONDS_ELAPSED}s, exceeding timeout of ${TIMEOUT}s. Killing..." >> "$LOG_FILE"
            kill -TERM $PYTHON_PID 2>/dev/null
            sleep 2
            
            # Force kill if still running
            if kill -0 $PYTHON_PID 2>/dev/null; then
                echo "$(date): Force killing $SCRIPT" >> "$LOG_FILE"
                kill -9 $PYTHON_PID 2>/dev/null
            fi
            break
        fi
    done
    
    # Capture the exit code
    wait $PYTHON_PID 2>/dev/null
    EXIT_CODE=$?
    
    echo "$(date): $SCRIPT stopped with exit code $EXIT_CODE" >> "$LOG_FILE"
    
    # Wait before restarting
    echo "$(date): Restarting in $RESTART_DELAY seconds..." >> "$LOG_FILE"
    sleep $RESTART_DELAY
done
