import pandas as pd
import numpy as np
from src.calculations.engine import CalculationEngine
import tempfile

def create_test_data():
    """Create test data for calculations."""
    # Drop dump (no headers)
    drop_dump = pd.DataFrame(['123456789012345'])
    
    # Price list
    price_list = pd.DataFrame({
        'Master_Model': ['iPhone 12', 'Samsung S21'],
        'Purchase_Price': [50000, 45000],
        'Valid_From': ['2023-01-01', '2023-01-01'],
        'Valid_To': ['2024-12-31', '2024-12-31']
    })
    
    # Scheme file
    scheme_file = pd.DataFrame({
        'Master_Model': ['iPhone 12', 'Samsung S21'],
        'Scheme_Type': ['Percentage', 'Flat'],
        'Scheme_Value': [5, 2000],  # 5% or flat ₹2000
        'Scheme_Start_Date': ['2024-01-01', '2024-01-01'],
        'Scheme_End_Date': ['2024-12-31', '2024-12-31']
    })
    
    # Sales data
    sales_data = pd.DataFrame({
        'IMEI': ['123456789012345', '987654321098765'],
        'Master_Model': ['iPhone 12', 'Samsung S21'],
        'Sell_Out_Date': ['2024-06-15', '2024-06-16'],
        'Purchase_Price': [50000, 45000],
        'Distributor': ['Dist A', 'Dist B']
    })
    
    return drop_dump, price_list, scheme_file, sales_data

def test_calculations():
    """Test the calculation engine."""
    try:
        drop_dump, price_list, scheme_file, sales_data = create_test_data()
        
        engine = CalculationEngine(drop_dump, price_list, scheme_file, sales_data)
        processed_data, errors = engine.run_calculations()
        
        # Basic checks
        assert len(processed_data) == 2
        assert 'Total_Incentive_Received' in processed_data.columns
        assert 'NLC' in processed_data.columns
        assert 'Drop' in processed_data.columns
        
        # Check drop detection
        assert processed_data.loc[0, 'Drop'] == 1  # First IMEI matches drop
        assert processed_data.loc[1, 'Drop'] == 0  # Second IMEI doesn't match
        
        # Check calculations are numeric
        assert pd.api.types.is_numeric_dtype(processed_data['Total_Incentive_Received'])
        assert pd.api.types.is_numeric_dtype(processed_data['NLC'])
        
        # Check NLC = Final_Price - Total_Incentive
        for idx, row in processed_data.iterrows():
            expected_nlc = row['Final_Price'] - row['Total_Incentive_Received']
            assert abs(row['NLC'] - expected_nlc) < 0.01
        
        print(f"Processed {len(processed_data)} records successfully")
        if errors:
            print(f"Errors encountered: {errors}")
        
        return True
        
    except Exception as e:
        print(f"Calculation test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_pivot_report():
    """Test pivot report generation."""
    try:
        drop_dump, price_list, scheme_file, sales_data = create_test_data()
        
        engine = CalculationEngine(drop_dump, price_list, scheme_file, sales_data)
        processed_data, _ = engine.run_calculations()
        pivot_data = engine.generate_pivot_report()
        
        assert len(pivot_data) > 0
        assert 'Distributor' in pivot_data.columns
        assert 'Total_Incentive_Received' in pivot_data.columns
        
        return True
        
    except Exception as e:
        print(f"Pivot report test failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("Testing calculations...")
    success = test_calculations() and test_pivot_report()
    print(f"Calculation tests: {'PASSED' if success else 'FAILED'}")