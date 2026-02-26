#!/bin/bash
# Disable problematic extensions causing extension host crashes
# Run this script to temporarily disable extensions that are causing issues

CURSOR_EXT_DIR="$HOME/.cursor/extensions"
SETTINGS_JSON="$HOME/Library/Application Support/Cursor/User/settings.json"

echo "Disabling problematic extensions..."

# Create settings.json backup
if [ -f "$SETTINGS_JSON" ]; then
    cp "$SETTINGS_JSON" "${SETTINGS_JSON}.backup.$(date +%Y%m%d_%H%M%S)"
    echo "Backed up settings.json"
fi

# Read current disabled extensions
if [ -f "$SETTINGS_JSON" ]; then
    DISABLED=$(grep -o '"extensions\.disabled":\s*\[.*\]' "$SETTINGS_JSON" 2>/dev/null || echo "")
else
    DISABLED=""
fi

# Extensions to disable (most problematic first)
EXTENSIONS_TO_DISABLE=(
    "ms-python.vscode-python-envs"  # TypeError during deactivation
    "redhat.vscode-xml"              # Configuration warnings and Canceled errors
)

echo ""
echo "Extensions to disable:"
for ext in "${EXTENSIONS_TO_DISABLE[@]}"; do
    echo "  - $ext"
done

echo ""
echo "To manually disable these extensions:"
echo "1. Open Cursor"
echo "2. Press Cmd+Shift+P"
echo "3. Type 'Extensions: Show Installed Extensions'"
echo "4. Search for each extension and click the gear icon > Disable"
echo ""
echo "Or add to settings.json:"
echo '{'
echo '  "extensions.disabled": ['
for ext in "${EXTENSIONS_TO_DISABLE[@]}"; do
    echo "    \"$ext\","
done
echo '  ]'
echo '}'




