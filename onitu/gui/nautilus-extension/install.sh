#!/bin/sh

BASEDIR=$(dirname $0)

mkdir -p ~/.icons/hicolor/48x48/emblems
cp $BASEDIR/icons/* ~/.icons/hicolor/48x48/emblems
mkdir -p ~/.local/share/nautilus-python/extensions
cp $BASEDIR/onitu-nautilus.py ~/.local/share/nautilus-python/extensions
nautilus -q

echo "You can now use the extension !"