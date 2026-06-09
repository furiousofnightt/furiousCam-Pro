#!/bin/bash

# FuriousCam Build Script for macOS and Linux

echo "============================================"
echo "   FuriousCam Pro - Build Script"
echo "============================================"
echo ""

# Check if PyInstaller is installed
python3 -c "import PyInstaller" >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "PyInstaller not found. Installing..."
    pip install pyinstaller
else
    echo "PyInstaller found."
fi

echo ""
echo "Building executable..."
echo ""

# Run PyInstaller with the spec file
pyinstaller furiousCam.spec --onedir

echo ""
echo "============================================"
echo "   Build complete!"
echo "============================================"
echo ""
echo "Executable location: dist/FuriousCam/FuriousCam"
echo ""
echo "To run:"
echo "  ./dist/FuriousCam/FuriousCam"
echo ""
