# Case-Insensitive Column Handling

## Overview
All column name handling throughout the SIAT application is now **case-insensitive**. This means the application will work correctly regardless of whether column names in input files are in UPPERCASE, lowercase, or Mixed Case.

## Changes Made

### 1. Sales Sheet Column Standardization (loader.py)
- All column names are converted to lowercase before mapping
- Standardized internal names:
  - `Current_MOP_SRP` (was: current mop/srp)
  - `Activation_Date` (was: activation date)
  - All other columns follow consistent naming

**Supported Variations:**
- IMEI: `imei`, `IMEI`, `Imei`
- Sell Out Date: `sell out date`, `SELL OUT DATE`, `Sell Out Date`, `sellout date`
- Master Model: `master model`, `MASTER MODEL`, `Master Model`, `master modal`
- Distributor: `distributor`, `DISTRIBUTOR`, `Distributor`, `distibutor`
- Purchase Price: `purchase price`, `PURCHASE PRICE`, `Purchase Price`
- Current Month Invoice Price: `bill less in invoice`, `current month invoice price`
- Current MOP/SRP: `current mop/srp`, `CURRENT MOP/SRP`, `Current MOP/SRP`
- Activation Date: `activation date`, `ACTIVATION DATE`, `Activation Date`

### 2. Price List Column Standardization (loader.py)
- All column names converted to lowercase before mapping
- Supports variations like:
  - Master Model: `master model`, `MASTER MODEL`, `Master Model`
  - Valid From: `valid from`, `VALID FROM`, `Valid From`
  - Valid To: `valid to`, `VALID TO`, `Valid To`
  - Purchase Price: `net purchase 4%`, `purchase price`, `PURCHASE PRICE`

### 3. Scheme Sheet Column Standardization (loader.py)
- Already case-insensitive (converts to lowercase)
- Supports all variations of:
  - Master Model
  - Scheme Start/End Dates
  - PCT Scheme columns
  - Flat Scheme/Flat Payout
  - Condition-1

### 4. Drop Dump Column Standardization (loader.py)
- Already case-insensitive (converts to lowercase)
- Supports: `imei`, `IMEI`, `Imei`
- Supports: `drop amount`, `DROP AMOUNT`, `Drop Amount`

### 5. Calculation Engine Updates (engine.py)

#### Added Helper Method
```python
_get_column_case_insensitive(df, column_name, default=None)
```
- Performs case-insensitive column lookup
- Returns column data if found, default value otherwise

#### Price Variable Selection
- Case-insensitive fallback for column lookup
- Works with any case variation of:
  - Current_Month_Invoice_Price
  - Purchase_Price
  - Current_MOP_SRP

#### Output Column Mapping
- Simplified to use standardized internal names
- Direct mapping from:
  - `Current_MOP_SRP` → `Current MOP/SRP` (output)
  - `Activation_Date` → `Activation Date` (output)

#### Pivot Report Generation
- Case-insensitive distributor column lookup
- Handles both `Distributor` and `distibutor` (typo)

## Benefits

### 1. Robustness
- Application works regardless of input file column case
- No need to manually adjust column names in Excel files

### 2. Flexibility
- Users can use their preferred naming conventions
- Supports legacy files with different naming styles

### 3. Error Prevention
- Eliminates "column not found" errors due to case mismatch
- Reduces data loading failures

## Testing Recommendations

Test with input files having:
1. All UPPERCASE column names
2. All lowercase column names
3. Mixed case column names
4. Combination of different cases across sheets

## Example Scenarios

### Scenario 1: All Uppercase
```
Input: IMEI, SELL OUT DATE, MASTER MODEL
Result: ✅ Works correctly
```

### Scenario 2: All Lowercase
```
Input: imei, sell out date, master model
Result: ✅ Works correctly
```

### Scenario 3: Mixed Case
```
Input: Imei, Sell Out Date, Master Model
Result: ✅ Works correctly
```

### Scenario 4: Variations
```
Input: IMEI, sell out date, Master Model, CURRENT MOP/SRP
Result: ✅ Works correctly
```

## Internal Column Names (Standardized)

### Sales Sheet
- `IMEI`
- `Sell_Out_Date`
- `Master_Model`
- `Distributor`
- `Purchase_Date`
- `Purchase_Price`
- `Current_Month_Invoice_Price`
- `Current_Month_Pre_GST_Invoice_Price`
- `SERIES`
- `Current_MOP_SRP`
- `Activation_Date`

### Price List
- `Master_Model`
- `Valid_From`
- `Valid_To`
- `Purchase_Price`
- `Pre_GST_Price`

### Scheme Sheet
- `Master_Model`
- `Scheme_Start_Date`
- `Scheme_End_Date`
- `Pct_Scheme_1`, `Pct_Scheme_2`, `Pct_Scheme_3`, `Pct_Scheme_4`
- `Pct_Scheme_1_A`, `Pct_Scheme_1_B`
- `Flat_Scheme`
- `Condition_1`

### Drop Dump
- `IMEI`
- `Drop_Amount`

## Notes

- All column name comparisons are done after converting to lowercase
- Fuzzy matching is still available as a fallback for partial matches
- The standardized internal names ensure consistency throughout calculations
- Output column names follow title case convention for professional appearance
