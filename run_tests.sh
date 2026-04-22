#!/bin/bash

# Script to run tests with coverage report
# This script will automatically install dependencies if needed

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Update Manager - Test Suite${NC}"
echo "=============================="
echo ""

# Check if we're in a virtual environment
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo -e "${YELLOW}Warning: Not in a virtual environment${NC}"
    echo "It's recommended to run: python3 -m venv venv && source venv/bin/activate"
    echo ""
fi

# Install dependencies if requirements file exists
if [ -f "requirements-dev.txt" ]; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install --break-system-packages -q -r requirements-dev.txt 2>/dev/null || pip install -q -r requirements-dev.txt
    echo -e "${GREEN}✓ Dependencies installed${NC}"
else
    echo -e "${RED}Error: requirements-dev.txt not found${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Running tests with coverage...${NC}"

# Run tests
python3 -m pytest \
    --cov=update_manager \
    --cov-report=term-missing \
    --cov-report=html \
    -v \
    tests/

PYTEST_EXIT_CODE=$?

echo ""
if [ $PYTEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo -e "${GREEN}✓ Coverage report generated in htmlcov/index.html${NC}"
else
    echo -e "${RED}✗ Some tests failed${NC}"
    exit $PYTEST_EXIT_CODE
fi

echo ""

