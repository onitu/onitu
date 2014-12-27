To install this extension:


Install 'python-nautilus' package
e.g.: sudo apt-get install python-nautilus

Create these dirs:
mkdir -p ~/.icons/hicolor/48x48/emblems

Copy icons:
cp icons/* ~/.icons/hicolor/48x48/emblems

Create these dirs:
mkdir -p ~/.local/share/nautilus-python/extensions

Copy the script:
cp onitu-nautilus.py ~/.local/share/nautilus-python/extensions

Reload nautilus: nautilus -q; nautilus


