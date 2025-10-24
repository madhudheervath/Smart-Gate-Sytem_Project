#!/bin/bash
# Installation Progress Checker

echo "================================"
echo "Face Recognition Installation"
echo "================================"
echo ""

# Check if process is running
if ps aux | grep -q "[p]ip install face-recognition"; then
    echo "⏳ Status: Installing (dlib compiling...)"
    echo ""
    echo "This typically takes 3-5 minutes."
    echo "You can continue working - server will auto-reload when done."
else
    echo "✅ Status: Installation complete or not running"
fi

echo ""
echo "Checking installed packages:"
echo "----------------------------"

source venv/bin/activate 2>/dev/null

# Check each package
packages=("face-recognition" "opencv-python" "Pillow" "dlib")

for pkg in "${packages[@]}"; do
    if python3 -c "import ${pkg//-/_}" 2>/dev/null; then
        version=$(pip show $pkg 2>/dev/null | grep "^Version:" | cut -d' ' -f2)
        echo "✅ $pkg - $version"
    else
        echo "⏳ $pkg - Not installed yet"
    fi
done

echo ""
echo "================================"
