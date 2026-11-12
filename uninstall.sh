#!/bin/sh
rm -rf "$HOME/.local/share/cvt"
rm -f "$HOME/.local/bin/cvt-app"
rm -f "$HOME/.local/share/applications/cvt.app.desktop"
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
echo "Removido."
