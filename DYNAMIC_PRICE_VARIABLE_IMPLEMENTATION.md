# Dynamic Price Variable for Final Price Calculation - Implementation Guide

## Overview
Implemented user-selectable price variable for FINAL PRICE FOR CALCULATION while maintaining brand-specific calculation logic.

## Feature Description

### User Control
Added dropdown in sidebar under "Conditions" section:
- **Label**: "Select to calculate - Final Price for Calculation"
- **Options**:
  1. Current Month Invoice Price (default)
  2. Purchase Price
  3. Current MOP/SRP

### Brand-Specific Logic (Preserved)

The brand-specific conditions remain intact. Only the price component is dynamic:

| Brand | Formula |
|-------|---------|
| **REDMI** | `{user_selected_price} - Drop` |
| **SAMSUNG** | `{user_selected_price} - Drop - Flat Payout` |
| **REALME** | `{user_selected_price} - Drop` |
| **OPPO** | `{user_selected_price} - Drop` |
| **Others** | `{user_selected_price} - Drop` |

Where `{user_selected_price}` is the value from the dropdown selection.

## Implementation Details

### 1. UI Changes (dashboard.py)

#### Added Dropdown (Lines 195-207)
```python
price_options = [
    "Current Month Invoice Price",
    "Purchase Price",
    "Current MOP/SRP"
]

selected_price_variable = st.sidebar.selectbox(
    "Select to calculate - Final Price for Calculation",
    price_options,
    index=0,
    help="Select which price field to use in Final Price calculation formula",
    key="price_variable_selector"
)
```

#### Pass to Engine (Line 330)
```python
self.calculation_engine = CalculationEngine(
    self.drop_dump, self.price_list,
    self.scheme_file, self.sales_data,
    brand=st.session_state.selected_brand,
    purchase_price_threshold=...,
    price_variable_column=st.session_state.price_variable_selector
)
```

### 2. Calculation Engine Changes (engine.py)

#### Constructor Update
Added parameter:
```python
price_variable_column: str = "Current Month Invoice Price"
```

#### Dynamic Price Selection (_step_5_6_tax_base method)

**Column Mapping**:
```python
price_column_mapping = {
    "Current Month Invoice Price": "Current_Month_Invoice_Price",
    "Purchase Price": "Purchase_Price",
    "Current MOP/SRP": "current mop/srp"
}
```

**Price Variable Extraction**:
```python
selected_column = price_column_mapping.get(self.price_variable_column)
price_variable = df[selected_column].fillna(0)
```

**Brand-Specific Application**:
```python
if brand_upper == "REDMI":
    df['Tax_Base_Final_Price'] = price_variable - df['Drop_Amount']
    
elif brand_upper == "SAMSUNG":
    df['Tax_Base_Final_Price'] = price_variable - df['Drop_Amount']
    df['Samsung_Adjustment_Needed'] = True  # Flat Payout deducted in Step 10
    
elif brand_upper in ["REALME", "OPPO"]:
    df['Tax_Base_Final_Price'] = price_variable - df['Drop_Amount']
    
else:
    df['Tax_Base_Final_Price'] = price_variable - df['Drop_Amount']
```

### 3. Data Loader Changes (loader.py)

Added mapping for "current mop/srp" column:
```python
'current mop/srp': 'current mop/srp',  # Keep as-is for price variable selection
```

## Usage Examples

### Example 1: SAMSUNG with Current MOP/SRP
**User Selection**:
- Brand: Samsung
- Price Variable: Current MOP/SRP

**Formula Applied**:
```
FINAL PRICE FOR CALCULATION = Current MOP/SRP - Drop - Flat Payout
```

### Example 2: REDMI with Purchase Price
**User Selection**:
- Brand: Redmi
- Price Variable: Purchase Price

**Formula Applied**:
```
FINAL PRICE FOR CALCULATION = Purchase Price - Drop
```

### Example 3: REALME with Current Month Invoice Price
**User Selection**:
- Brand: Realme
- Price Variable: Current Month Invoice Price

**Formula Applied**:
```
FINAL PRICE FOR CALCULATION = Current Month Invoice Price - Drop
```

## Fallback Handling

### Missing Column Handling
If "Current MOP/SRP" is selected but column doesn't exist:
1. System searches for variations: 'current mop/srp', 'Current MOP/SRP', 'current_mop_srp', 'Current_MOP_SRP'
2. If not found, falls back to "Current_Month_Invoice_Price"
3. Logs warning message

### Default Value
If no selection is made or error occurs:
- Default: "Current Month Invoice Price"

## Downstream Impact

### ✅ No Changes Required
All downstream calculations continue to work:
1. **PRE GST OF FINAL PRICE CALCULATION** = FINAL PRICE FOR CALCULATION / 1.18
2. **Amount PCT Schemes** = (PCT Scheme % / 100) × PRE GST OF FINAL PRICE CALCULATION
3. **NLC** = FINAL PRICE FOR CALCULATION - Total Incentive Received
4. **Margin** = Purchase Price - NLC

## Testing Checklist

- [ ] Select "Current Month Invoice Price" → Verify calculation
- [ ] Select "Purchase Price" → Verify calculation
- [ ] Select "Current MOP/SRP" → Verify calculation
- [ ] Test with REDMI brand → Verify Drop subtraction
- [ ] Test with SAMSUNG brand → Verify Drop + Flat Payout subtraction
- [ ] Test with REALME brand → Verify Drop subtraction
- [ ] Test with OPPO brand → Verify Drop subtraction
- [ ] Test with other brands → Verify Drop subtraction
- [ ] Verify PRE GST calculation remains correct
- [ ] Verify Amount PCT Schemes calculate correctly
- [ ] Verify NLC calculation remains correct
- [ ] Test with missing "Current MOP/SRP" column → Verify fallback

## Files Modified

1. **src/ui/dashboard.py**
   - Added price variable dropdown in Conditions section
   - Passed selection to CalculationEngine

2. **src/calculations/engine.py**
   - Added price_variable_column parameter
   - Implemented dynamic price selection in _step_5_6_tax_base()
   - Maintained brand-specific logic

3. **src/data/loader.py**
   - Added "current mop/srp" column mapping

## Backward Compatibility

✅ Fully backward compatible:
- Default value: "Current Month Invoice Price"
- Existing workbooks work without changes
- Brand-specific logic preserved
- All downstream calculations unchanged

## Benefits

1. **Flexibility**: Users can choose which price to use in calculations
2. **Brand Logic Preserved**: Samsung still subtracts Flat Payout, etc.
3. **Easy to Use**: Simple dropdown selection
4. **Transparent**: Logs show which price variable is being used
5. **Safe**: Fallback handling for missing columns
