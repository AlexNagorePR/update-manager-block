.PHONY: help install install-dev test test-verbose test-coverage clean setup

help:
	@echo "Update Manager - Available Commands"
	@echo "===================================="
	@echo ""
	@echo "  make setup              - Create virtual environment and install dependencies"
	@echo "  make install            - Install runtime dependencies"
	@echo "  make install-dev        - Install development dependencies"
	@echo "  make test               - Run tests"
	@echo "  make test-verbose       - Run tests with verbose output"
	@echo "  make test-coverage      - Run tests and generate coverage report"
	@echo "  make clean              - Clean build artifacts and cache"
	@echo ""

setup:
	@echo "Setting up development environment..."
	@python3 -m venv venv
	@echo ""
	@echo "Virtual environment created!"
	@echo "Activate it with: source venv/bin/activate"
	@echo ""

install:
	@echo "Installing runtime dependencies..."
	pip install -r requirements.txt
	@echo "✓ Done!"

install-dev:
	@echo "Installing development dependencies..."
	pip install -r requirements-dev.txt
	@echo "✓ Done!"

test:
	@python3 -m pytest -v tests/

test-verbose:
	@python3 -m pytest -vv --tb=long tests/

test-coverage:
	@chmod +x run_tests.sh
	@./run_tests.sh

clean:
	@echo "Cleaning up..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
	rm -rf .pytest_cache 2>/dev/null || true
	rm -rf .coverage 2>/dev/null || true
	rm -rf htmlcov 2>/dev/null || true
	rm -rf build 2>/dev/null || true
	rm -rf dist 2>/dev/null || true
	rm -rf *.egg-info 2>/dev/null || true
	@echo "✓ Cleanup done!"
