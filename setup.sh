#!/bin/bash

echo "=========================================="
echo "Medical Voice Agent - Setup Script"
echo "=========================================="

# Check Python version
echo "Checking Python version..."
python3 --version

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "Installing requirements..."
pip install -r requirements.txt

# Create necessary directories
echo "Creating directories..."
mkdir -p encounters
mkdir -p recordings
mkdir -p logs

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "To run the system:"
echo "1. Activate venv: source venv/bin/activate"
echo "2. Test system: python test_system.py"
echo "3. Run server: python app.py"
echo "4. Open browser: http://localhost:8000"
echo ""
echo "=========================================="