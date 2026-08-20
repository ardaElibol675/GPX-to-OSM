#!/usr/bin/env bash
# gpx_to_osm CLI kurulum betiği
# /usr/local/bin altına bir sembolik link oluşturarak scripti "gpx_to_osm"
# komutuyla her yerden çalıştırılabilir hale getirir.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="$SCRIPT_DIR/src/gpx_to_osm.py"
TARGET="/usr/local/bin/gpx_to_osm"

chmod +x "$SOURCE"

if [ -w "$(dirname "$TARGET")" ]; then
    ln -sf "$SOURCE" "$TARGET"
else
    sudo ln -sf "$SOURCE" "$TARGET"
fi

echo "Kurulum tamamlandı. Artık 'gpx_to_osm <dosya.gpx>' komutunu kullanabilirsin."
