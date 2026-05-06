import pandas as pd
import numpy as np
from src.data.loader import DataLoader
import tempfile
import os

def test_data_loading():
    """Test data loading functionality."""
    try:
        loader = DataLoader()
        
        # Create test data
        test_data = pd.DataFrame({
            'IMEI': ['123456789012345', '987654321098765'],
            'Master_Model': ['iPhone 12', 'Samsung S21'],
            'Sell_Out_Date': ['2024-01-01', '2024-01-02'],
            'Purchase_Price': [50000, 45000],
            'Distributor': ['Dist A', 'Dist B']
        })
        
        # Test CSV loading
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
            test_data.to_csv(f.name, index=False)
            loaded_data = loader.load_excel_file(f.name, has_header=True, header_row=0)
            os.unlink(f.name)
        
        assert len(loaded_data) == 2
        assert 'IMEI' in loaded_data.columns
        
        # Test Excel loading (if openpyxl available)
        try:
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
                test_data.to_excel(f.name, index=False)
                loaded_data = loader.load_excel_file(f.name, has_header=True, header_row=0)
                os.unlink(f.name)
            
            assert len(loaded_data) == 2
            assert 'IMEI' in loaded_data.columns
        except ImportError:
            print("Openpyxl not available, skipping Excel test")
        
        return True
        
    except Exception as e:
        print(f"Data loading test failed: {str(e)}")
        return False

def test_drop_dump_loading():
    """Test loading drop dump without headers."""
    try:
        loader = DataLoader()
        
        # Create test drop dump (no headers)
        drop_data = pd.DataFrame(['123456789012345', '987654321098765'])
        
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
            drop_data.to_csv(f.name, header=False, index=False)
            loaded_data = loader.load_drop_dump(f.name)
            os.unlink(f.name)
        
        assert len(loaded_data) == 2
        return True
        
    except Exception as e:
        print(f"Drop dump loading test failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("Testing data loading...")
    success = test_data_loading() and test_drop_dump_loading()
    print(f"Data loading tests: {'PASSED' if success else 'FAILED'}")