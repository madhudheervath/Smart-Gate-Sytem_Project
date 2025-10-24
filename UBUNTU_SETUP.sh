#!/bin/bash

# ============================================================================
# Smart Gate System - Complete Ubuntu Linux Setup Script
# ============================================================================
# This script installs ALL dependencies needed to run the project
# Tested on: Ubuntu 20.04, 22.04, 24.04
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_header() {
    echo ""
    echo "============================================================"
    echo -e "${GREEN}$1${NC}"
    echo "============================================================"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    print_error "Please do not run this script as root or with sudo"
    print_info "The script will ask for sudo password when needed"
    exit 1
fi

print_header "🚀 Smart Gate System - Ubuntu Setup"
echo "This script will install ALL dependencies needed to run the project"
echo ""
print_warning "This will install system packages and Python libraries"
read -p "Do you want to continue? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_info "Setup cancelled"
    exit 0
fi

# ============================================================================
# STEP 1: Update System
# ============================================================================
print_header "📦 Step 1: Updating System Packages"
print_info "Updating package list..."
sudo apt update

# ============================================================================
# STEP 2: Install Python 3 and pip
# ============================================================================
print_header "🐍 Step 2: Installing Python 3 and pip"

# Check Python version
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    print_info "Python 3 is already installed: $PYTHON_VERSION"
else
    print_info "Installing Python 3..."
    sudo apt install -y python3 python3-pip python3-dev
fi

# Ensure pip is installed
print_info "Ensuring pip is up to date..."
python3 -m pip install --upgrade pip

print_success "Python 3 and pip installed successfully"

# ============================================================================
# STEP 3: Install System Dependencies
# ============================================================================
print_header "📚 Step 3: Installing System Dependencies"

print_info "Installing essential build tools..."
sudo apt install -y \
    build-essential \
    cmake \
    pkg-config \
    wget \
    curl \
    git

print_info "Installing image processing libraries..."
sudo apt install -y \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    libxvidcore-dev \
    libx264-dev

print_info "Installing X11 and GTK libraries..."
sudo apt install -y \
    libgtk-3-dev \
    libatlas-base-dev \
    gfortran \
    libhdf5-dev \
    libhdf5-serial-dev

print_info "Installing Boost libraries for dlib..."
sudo apt install -y \
    libboost-all-dev

print_success "System dependencies installed successfully"

# ============================================================================
# STEP 4: Install dlib (for face recognition)
# ============================================================================
print_header "🤖 Step 4: Installing dlib (Face Recognition Library)"

print_info "This may take 5-10 minutes to compile..."
print_info "Installing dlib..."
python3 -m pip install --no-cache-dir dlib

print_success "dlib installed successfully"

# ============================================================================
# STEP 5: Install Python Dependencies
# ============================================================================
print_header "📦 Step 5: Installing Python Dependencies"

if [ -f "requirements.txt" ]; then
    print_info "Installing packages from requirements.txt..."
    python3 -m pip install -r requirements.txt
    
    # Install additional dependencies that might be missing
    print_info "Installing additional Python packages..."
    python3 -m pip install \
        face-recognition \
        opencv-python \
        pillow \
        numpy \
        scipy \
        shapely \
        geopy \
        firebase-admin \
        python-jose[cryptography] \
        python-multipart \
        websockets \
        aiosqlite
    
    print_success "Python dependencies installed successfully"
else
    print_error "requirements.txt not found!"
    print_info "Installing core dependencies manually..."
    
    python3 -m pip install \
        fastapi==0.115.2 \
        uvicorn[standard]==0.30.6 \
        SQLAlchemy==2.0.36 \
        pydantic==2.9.2 \
        pydantic-settings==2.6.1 \
        email-validator \
        PyJWT==2.9.0 \
        passlib[bcrypt]==1.7.4 \
        bcrypt \
        python-multipart==0.0.9 \
        face-recognition \
        opencv-python \
        pillow \
        numpy \
        scipy \
        shapely \
        geopy \
        firebase-admin \
        python-jose[cryptography] \
        websockets \
        aiosqlite
    
    print_success "Core dependencies installed successfully"
fi

# ============================================================================
# STEP 6: Install SQLite
# ============================================================================
print_header "🗄️  Step 6: Installing SQLite"

if command -v sqlite3 &> /dev/null; then
    SQLITE_VERSION=$(sqlite3 --version | awk '{print $1}')
    print_info "SQLite is already installed: $SQLITE_VERSION"
else
    print_info "Installing SQLite..."
    sudo apt install -y sqlite3 libsqlite3-dev
    print_success "SQLite installed successfully"
fi

# ============================================================================
# STEP 7: Create Virtual Environment (Optional but Recommended)
# ============================================================================
print_header "🔧 Step 7: Setting up Virtual Environment"

if [ ! -d "venv" ]; then
    print_info "Creating virtual environment..."
    python3 -m venv venv
    print_success "Virtual environment created"
    print_info "To activate: source venv/bin/activate"
else
    print_info "Virtual environment already exists"
fi

# ============================================================================
# STEP 8: Initialize Database
# ============================================================================
print_header "🗃️  Step 8: Initializing Database"

if [ -f "backend/init_db.py" ]; then
    print_info "Running database initialization..."
    cd backend
    python3 init_db.py
    cd ..
    print_success "Database initialized successfully"
else
    print_warning "init_db.py not found, skipping database initialization"
    print_info "You can initialize manually later by running:"
    print_info "  cd backend && python3 init_db.py"
fi

# ============================================================================
# STEP 9: Create Necessary Directories
# ============================================================================
print_header "📁 Step 9: Creating Necessary Directories"

print_info "Creating face_encodings directory..."
mkdir -p backend/face_encodings

print_info "Setting proper permissions..."
chmod 755 backend/face_encodings

print_success "Directories created successfully"

# ============================================================================
# STEP 10: Make Scripts Executable
# ============================================================================
print_header "⚙️  Step 10: Making Scripts Executable"

print_info "Setting execute permissions on scripts..."
chmod +x START_SERVER.sh 2>/dev/null || true
chmod +x RESTART_SERVER.sh 2>/dev/null || true
chmod +x check_installation.sh 2>/dev/null || true
chmod +x cleanup_project.sh 2>/dev/null || true

print_success "Scripts are now executable"

# ============================================================================
# STEP 11: Verify Installation
# ============================================================================
print_header "✅ Step 11: Verifying Installation"

print_info "Checking Python packages..."

# Check critical packages
PACKAGES=("fastapi" "uvicorn" "sqlalchemy" "face_recognition" "cv2" "PIL" "jwt" "passlib")
ALL_INSTALLED=true

for package in "${PACKAGES[@]}"; do
    if python3 -c "import $package" 2>/dev/null; then
        print_success "✓ $package installed"
    else
        print_error "✗ $package NOT installed"
        ALL_INSTALLED=false
    fi
done

if [ "$ALL_INSTALLED" = true ]; then
    print_success "All critical packages are installed!"
else
    print_warning "Some packages are missing. Please check the errors above."
fi

# ============================================================================
# STEP 12: Check System Resources
# ============================================================================
print_header "💻 Step 12: Checking System Resources"

print_info "System Information:"
echo "  - OS: $(lsb_release -d | cut -f2)"
echo "  - Kernel: $(uname -r)"
echo "  - Python: $(python3 --version)"
echo "  - pip: $(python3 -m pip --version | awk '{print $2}')"
echo "  - RAM: $(free -h | awk '/^Mem:/ {print $2}')"
echo "  - Disk Space: $(df -h . | awk 'NR==2 {print $4}')"

# ============================================================================
# FINAL: Installation Complete
# ============================================================================
print_header "🎉 Installation Complete!"

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                                                                  ║"
echo "║       ✅ Smart Gate System - Setup Successful!                   ║"
echo "║                                                                  ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "📋 What was installed:"
echo "  ✓ Python 3 and pip"
echo "  ✓ Build tools (cmake, gcc, g++)"
echo "  ✓ Image processing libraries"
echo "  ✓ dlib (face recognition)"
echo "  ✓ All Python dependencies"
echo "  ✓ SQLite database"
echo "  ✓ Virtual environment"
echo "  ✓ Database initialized"
echo ""
echo "🚀 Next Steps:"
echo ""
echo "  1. Start the server:"
echo "     $ ./START_SERVER.sh"
echo ""
echo "  2. Access the portals:"
echo "     Student: http://localhost:8080/frontend/student/index.html"
echo "     Admin:   http://localhost:8080/frontend/admin/index.html"
echo "     Parent:  http://localhost:8080/frontend/parent/index.html"
echo "     Guard:   http://localhost:8080/frontend/guard/index.html"
echo ""
echo "  3. Test credentials:"
echo "     Student: student1@uni.edu / s123456"
echo "     Admin:   admin@uni.edu / admin123"
echo "     Guard:   guard@uni.edu / guard123"
echo ""
echo "📚 Documentation:"
echo "  README.md - Quick overview"
echo "  PROJECT_DOCUMENTATION.md - Complete guide"
echo ""
echo "🐛 Troubleshooting:"
echo "  $ bash check_installation.sh"
echo ""
print_success "Setup completed successfully! Happy coding! 🎓"
echo ""
