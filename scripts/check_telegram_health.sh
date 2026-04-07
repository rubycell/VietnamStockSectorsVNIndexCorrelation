#!/usr/bin/env bash
# Telegram provider health check for OpenClaw.
#
# Checks docker compose logs for recent Telegram activity (last 10 minutes).
# If no activity is found, restarts the OpenClaw container.
#
# Designed to run via cron every 10 minutes:
#   */10 * * * * /path/to/check_telegram_health.sh >> /path/to/telegram-health.log 2>&1

set -euo pipefail

PROJECT_DIR="/home/mike/workspace/github/vnstocksectorvnindexcorrelation"
LOG_PREFIX="$(date '+%Y-%m-%d %H:%M:%S')"
LOOKBACK="12m"  # slightly wider than 10m cron interval to avoid race

cd "$PROJECT_DIR"

# Check if the openclaw container is running at all
if ! docker compose ps openclaw 2>/dev/null | grep -q "Up"; then
    echo "$LOG_PREFIX [WARN] openclaw container not running — starting"
    docker compose up -d openclaw 2>&1
    exit 0
fi

# Look for any Telegram activity in the last LOOKBACK minutes.
# Activity includes: starting provider, sendMessage, received updates, polling
TELEGRAM_LINES=$(docker compose logs openclaw --since "$LOOKBACK" 2>/dev/null \
    | grep -c "\[telegram\]" || true)

if [ "$TELEGRAM_LINES" -gt 0 ]; then
    echo "$LOG_PREFIX [OK] Telegram active ($TELEGRAM_LINES log lines in last $LOOKBACK)"
    exit 0
fi

# No Telegram activity — restart
echo "$LOG_PREFIX [ALERT] No Telegram activity in last $LOOKBACK — restarting openclaw"
docker compose restart openclaw 2>&1
sleep 15

# Verify the restart worked
AFTER_RESTART=$(docker compose logs openclaw --since 20s 2>/dev/null \
    | grep -c "starting provider.*rubynewcoinsbot" || true)

if [ "$AFTER_RESTART" -gt 0 ]; then
    echo "$LOG_PREFIX [RECOVERED] Telegram provider started after restart"
else
    echo "$LOG_PREFIX [FAIL] Telegram provider did NOT start after restart — manual intervention needed"
fi
