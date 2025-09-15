#!/bin/bash

# HIPAA Voice Agent - Manual Testing Startup Script
# No-Hardware Profile (Built-in mic + speakers)

echo "=========================================="
echo "HIPAA VOICE AGENT - MANUAL TEST MODE"
echo "=========================================="
echo ""

# Check for required files
echo "✓ Checking environment..."
if [ ! -f .env ]; then
    echo "❌ ERROR: .env file not found!"
    echo "Please ensure API keys are configured."
    exit 1
fi

if [ ! -f .env.no_hardware ]; then
    echo "⚠️  WARNING: .env.no_hardware not found, using defaults"
fi

# Source the no-hardware profile if it exists
if [ -f .env.no_hardware ]; then
    echo "✓ Loading no-hardware profile..."
    set -a
    source .env.no_hardware
    set +a
fi

# Load main environment
echo "✓ Loading API keys..."
set -a
source .env
set +a

# Check API keys
if [ -z "$DEEPGRAM_API_KEY" ]; then
    echo "❌ ERROR: DEEPGRAM_API_KEY not set!"
    exit 1
fi

if [ -z "$HUGGINGFACE_API_KEY" ]; then
    echo "❌ ERROR: HUGGINGFACE_API_KEY not set!"
    exit 1
fi

echo "✓ API keys configured"
echo ""

# Set testing defaults
export DEFAULT_LATENCY_P95_MS=1700
export TEST_MODE=true
export LOG_LEVEL=DEBUG

echo "Configuration:"
echo "  - Mode: No-Hardware (built-in mic/speakers)"
echo "  - PTT: SHIFT key required"
echo "  - Duplex: Half (ASR paused during TTS)"
echo "  - Speaker-Safe: ENABLED"
echo "  - Latency Target: 1700ms P95"
echo ""

echo "Starting services..."
echo "=========================================="
echo ""

# Start the FastAPI server
echo "🚀 Starting web server on http://localhost:8000"
echo ""
echo "INSTRUCTIONS:"
echo "  1. Open http://localhost:8000 in your browser"
echo "  2. Grant microphone permissions when prompted"
echo "  3. Hold SHIFT key while speaking"
echo "  4. Follow MANUAL_TESTING_GUIDE.md for test cases"
echo ""
echo "Press Ctrl+C to stop the server"
echo "=========================================="
echo ""

# Run the app
python app.py