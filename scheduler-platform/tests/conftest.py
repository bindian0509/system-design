"""
Conftest for pytest configuration.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure test environment
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///test.db"  # Use SQLite for tests
os.environ["LOG_LEVEL"] = "WARNING"
