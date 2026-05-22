#!/usr/bin/env python3
"""
SIAT - Sales & Incentive Automation Tool
Streamlit Cloud Entry Point

This is the main entry point for Streamlit Cloud deployment.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Import and run the dashboard
from ui.dashboard import main

if __name__ == "__main__":
    main()
