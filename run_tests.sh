#!/bin/bash

# Script to run tests with coverage report

set -e

echo "Running tests with coverage..."
python -m pytest -p no:launch_testing_ros_pytest_entrypoint --cov=. --cov-report=term-missing --cov-report=html tests/

echo ""
echo "Coverage report generated in htmlcov/index.html"

