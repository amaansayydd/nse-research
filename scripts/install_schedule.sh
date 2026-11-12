#!/bin/zsh
# Install (or reinstall) the daily launchd job for the current user.
set -e
SRC="$(cd "$(dirname "$0")" && pwd)/com.nse-research.daily.plist"
DST="$HOME/Library/LaunchAgents/com.nse-research.daily.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/nse_production"
launchctl bootout "gui/$(id -u)/com.nse-research.daily" 2>/dev/null || true
cp "$SRC" "$DST"
launchctl bootstrap "gui/$(id -u)" "$DST"
launchctl print "gui/$(id -u)/com.nse-research.daily" | grep -E "state|path|program" | head -5
echo "installed. To remove: launchctl bootout gui/$(id -u)/com.nse-research.daily && rm $DST"
