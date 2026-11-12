#!/bin/sh
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.local/share/cvt"

mkdir -p "$DEST" "$HOME/.local/bin" "$HOME/.local/share/applications"

rm -rf "$DEST/conv"
cp -r "$DIR/conv" "$DEST/conv"
find "$DEST/conv" -name __pycache__ -type d -exec rm -rf {} +

cat > "$HOME/.local/bin/cvt-app" <<EOF
#!/bin/sh
cd "$DEST" && exec python3 -m conv "\$@"
EOF
chmod +x "$HOME/.local/bin/cvt-app"

cp "$DIR/cvt.app.desktop" "$HOME/.local/share/applications/cvt.app.desktop"
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

echo "Instalado. Rode 'cvt-app' ou procure por 'cvt' no launcher."
