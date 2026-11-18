#!/usr/bin/env bash
# cc-action.sh <command...> - Run a control-center tile's command and note that the change
# came from the panel itself, so cc-sync.sh doesn't refresh the panel for it.
touch "${XDG_RUNTIME_DIR:-/tmp}/cc-own-action"
exec "$@"
