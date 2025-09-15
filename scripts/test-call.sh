#!/bin/bash

# Test Call Shell Wrapper
# Makes a test call to the HIPAA voice agent

set -euo pipefail

# Default values
PHONE_NUMBER="${1:-}"
SCENARIO="${2:-default}"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Check if phone number provided
if [ -z "$PHONE_NUMBER" ]; then
    echo -e "${RED}Error: Phone number required${NC}"
    echo "Usage: $0 <phone_number> [scenario]"
    echo ""
    echo "Available scenarios:"
    echo "  - default     : Basic connectivity test"
    echo "  - appointment : Test appointment booking"
    echo "  - results     : Test lab results inquiry"
    echo "  - refill      : Test prescription refill"
    echo "  - emergency   : Test emergency handling"
    echo ""
    echo "Example: $0 +15025551234 appointment"
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required${NC}"
    exit 1
fi

# Check if test script exists
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_SCRIPT="${SCRIPT_DIR}/test-call.py"

if [ ! -f "$TEST_SCRIPT" ]; then
    echo -e "${RED}Error: Test script not found at $TEST_SCRIPT${NC}"
    exit 1
fi

# Run the test call
echo -e "${GREEN}Starting test call to $PHONE_NUMBER${NC}"
echo "Scenario: $SCENARIO"
echo ""

python3 "$TEST_SCRIPT" "$PHONE_NUMBER" "$SCENARIO"
