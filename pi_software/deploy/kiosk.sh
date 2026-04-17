#!/bin/bash
# Launch Chromium in kiosk mode pointing at the FieldCore dashboard.
# Waits for Flask to be ready before opening the browser.

URL="http://localhost:5001"
MAX_WAIT=30

echo "Waiting for Flask at $URL ..."
for i in $(seq 1 $MAX_WAIT); do
    if curl -s -o /dev/null -w "%{http_code}" "$URL/api/health" | grep -q "200"; then
        echo "Flask is ready."
        break
    fi
    sleep 1
done

# Hide mouse cursor after 3 seconds of inactivity
unclutter -idle 3 &

# Detect Chromium binary (Pi OS Bookworm+ uses `chromium`, older uses `chromium-browser`)
if command -v chromium >/dev/null 2>&1; then
    BROWSER=chromium
elif command -v chromium-browser >/dev/null 2>&1; then
    BROWSER=chromium-browser
else
    echo "ERROR: no chromium binary found. Install with: sudo apt install -y chromium" >&2
    exit 1
fi

# Launch Chromium in kiosk mode
exec "$BROWSER" \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --incognito \
    --disable-session-crashed-bubble \
    --disable-translate \
    --no-first-run \
    "$URL"
