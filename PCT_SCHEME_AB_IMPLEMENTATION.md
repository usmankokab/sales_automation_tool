# PCT Scheme-1 A/B Implementation Guide

## Overview
Implemented conditional PCT Scheme-1 selection based on Purchase Price threshold and CONDITION-1 column in scheme sheet.

## Features Implemented

### 1. Scheme Sheet Column Mappings (loader.py)
Added support for new columns:
- **Pct_Scheme_1_A**: Variations accepted
  - "pct scheme -1 (a)", "pct scheme -1(a)", "pct scheme -1 a"
  - "pct scheme-1 (a)", "pct scheme-1(a)", "pct scheme-1 a"
  
- **Pct_Scheme_1_B**: Variations accepted
  - "pct scheme -1 (b)", "pct scheme -1(b)", "pct scheme -1 b"
  - "pct scheme-1 (b)", "pct scheme-1(b)", "pct scheme-1 b"

- **Condition_1**: Variations accepted
  - "condition-1", "condition -1", "condition_1", "condition 1", "condition1"

- **Flat_Scheme**: Added new variation
  - "flat payout" (in addition to existing: "flat schme", "flat scheme", "flat_scheme", "flat")

### 2. Calculation Engine Logic (engine.py)

#### Constructor Update
- Added `purchase_price_threshold` parameter (Optional[float])
- Stores threshold for use in scheme application

#### Scheme Application Logic (_step_7_8_scheme_application)
Implements the following decision tree:

```
1. Check CONDITION-1 value for each scheme row
   
2. IF CONDITION-1 = "PRICE SLAB" (case-insensitive):
   - Check if Pct_Scheme_1_A and Pct_Scheme_1_B columns exist
   - IF threshold provided:
     - Purchase_Price <= threshold → Use Pct_Scheme_1_A
     - Purchase_Price > threshold → Use Pct_Scheme_1_B
   - IF threshold NOT provided:
     - Use Pct_Scheme_1_A (fallback)
   
3. ELSE IF CONDITION-1 ≠ "PRICE SLAB" (or empty/missing):
   - Always use Pct_Scheme_1_A if it exists
   - IF Pct_Scheme_1_A doesn't exist → fallback to Pct_Scheme_1
   
4. IF no A/B columns exist:
   - Use original Pct_Scheme_1 (current behavior)
```

### 3. Dashboard UI (dashboard.py)

#### New "Conditions" Section
Added between "Brand Selection" and "Workbook Upload":
- **Purchase Price Threshold** number input
  - Min value: 0.0
  - Step: 100.0
  - Optional (leave as 0 if not applicable)
  - Stored in session_state.purchase_price_threshold

#### Validation Logic
Added `_validate_scheme_ab_logic()` method:
- Runs before processing calculations
- Checks if:
  1. Pct_Scheme_1_A or Pct_Scheme_1_B columns exist
  2. Any values present in A/B columns
  3. CONDITION-1 contains "PRICE SLAB" in any row
  4. Threshold is missing when PRICE SLAB condition exists
- **Blocks processing** with error message if validation fails

#### Error Message
```
⚠️ Purchase Price threshold is required because scheme sheet contains 
PCT Scheme-1 (A)/(B) with PRICE SLAB condition. Please enter threshold 
value in the Conditions section or correct scheme headings.
```

## Usage Examples

### Example 1: PRICE SLAB Condition
**Scheme Sheet:**
| Master Model | CONDITION-1 | PCT Scheme -1 (A) | PCT Scheme -1 (B) |
|--------------|-------------|-------------------|-------------------|
| Model X      | PRICE SLAB  | 2.5               | 3.0               |

**User Input:** Threshold = 10000

**Result:**
- Sales with Purchase_Price ≤ 10000 → Get 2.5% scheme
- Sales with Purchase_Price > 10000 → Get 3.0% scheme

### Example 2: No PRICE SLAB Condition
**Scheme Sheet:**
| Master Model | CONDITION-1 | PCT Scheme -1 (A) | PCT Scheme -1 (B) |
|--------------|-------------|-------------------|-------------------|
| Model Y      | STANDARD    | 2.0               | 2.5               |

**Result:**
- All sales → Get 2.0% scheme (always uses A when not PRICE SLAB)

### Example 3: No A/B Columns
**Scheme Sheet:**
| Master Model | PCT Scheme -1 |
|--------------|---------------|
| Model Z      | 2.5           |

**Result:**
- All sales → Get 2.5% scheme (original behavior)

## Technical Details

### Column Detection
- Case-insensitive matching
- Whitespace tolerant
- Supports multiple naming conventions

### PRICE SLAB Detection
Accepted variations (case-insensitive):
- "price slab"
- "priceslab"
- "price_slab"
- "PRICE SLAB"

### Percentage Handling
- Auto-detects decimal (0.025) vs percentage (2.5) format
- Displays with % symbol in output
- Calculates correctly regardless of input format

## Files Modified

1. **src/data/loader.py**
   - Added Pct_Scheme_1_A, Pct_Scheme_1_B, Condition_1 mappings
   - Added "flat payout" variation for Flat_Scheme

2. **src/calculations/engine.py**
   - Added purchase_price_threshold parameter to constructor
   - Implemented A/B selection logic in apply_scheme() function
   - Added CONDITION-1 checking logic

3. **src/ui/dashboard.py**
   - Added "Conditions" section with threshold input
   - Added _validate_scheme_ab_logic() validation method
   - Passes threshold to CalculationEngine
   - Blocks processing if validation fails

## Testing Checklist

- [ ] Upload scheme with A/B columns and PRICE SLAB condition
- [ ] Verify error appears when threshold is empty
- [ ] Enter threshold and verify processing succeeds
- [ ] Verify correct scheme selection based on Purchase Price
- [ ] Test with CONDITION-1 ≠ "PRICE SLAB" (should always use A)
- [ ] Test with no A/B columns (should use original PCT Scheme-1)
- [ ] Test with various column name variations
- [ ] Verify percentage display shows % symbol
- [ ] Verify calculations are correct

## Backward Compatibility

✅ Fully backward compatible:
- If no A/B columns exist → Uses original PCT Scheme-1
- If A/B columns exist but no CONDITION-1 → Uses A by default
- Existing workbooks without A/B logic continue to work unchanged
