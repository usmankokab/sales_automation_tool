#!/usr/bin/env python3
"""
SIAT - Sales & Incentive Automation Tool

Main application entry point for the Sales & Incentive Automation Tool.
This tool automates the reconciliation of mobile phone sales data by
calculating price protections, promotional schemes, and Net Landing Costs.

Usage:
    python main.py                    # Run the Streamlit dashboard
    python main.py --cli              # Run command-line interface
    python main.py --test             # Run basic tests
"""

import argparse
import sys
import logging
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Configure logging
log_file = 'siat_application.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()  # Also log to console
    ]
)

logger = logging.getLogger(__name__)
logger.info("SIAT Application started")

from ui.dashboard import main as dashboard_main

def main():
    """Main application entry point."""
    parser = argparse.ArgumentParser(
        description="SIAT - Sales & Incentive Automation Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--cli',
        action='store_true',
        help='Run command-line interface instead of dashboard'
    )
    
    parser.add_argument(
        '--test',
        action='store_true',
        help='Run basic validation tests'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='SIAT v1.0'
    )
    
    args = parser.parse_args()
    
    if args.test:
        run_tests()
    elif args.cli:
        run_cli()
    else:
        # Default: run dashboard
        dashboard_main()

def run_cli():
    """Run command-line interface for batch processing."""
    print("SIAT Command-Line Interface")
    print("=" * 40)
    
    # CLI implementation would go here for batch processing
    # For now, direct to dashboard
    print("CLI interface not yet implemented. Please use the dashboard.")
    print("Run 'python main.py' to start the dashboard.")

def run_tests():
    """Run basic validation tests."""
    print("Running SIAT validation tests...")
    print("=" * 40)
    
    try:
        # Import test modules
        from tests.test_data_loader import test_data_loading
        from tests.test_calculations import test_calculations
        
        # Run tests
        print("✓ Data loading tests: PASSED" if test_data_loading() else "✗ Data loading tests: FAILED")
        print("✓ Calculation tests: PASSED" if test_calculations() else "✗ Calculation tests: FAILED")
        
        print("\nAll tests completed!")
        
    except ImportError:
        print("✗ Test modules not found. Make sure test files are in place.")
    except Exception as e:
        print(f"✗ Test execution failed: {str(e)}")

if __name__ == "__main__":
    main()