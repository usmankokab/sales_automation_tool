import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple, List
import logging
from fuzzywuzzy import fuzz
from fuzzywuzzy.process import extractOne
import re

logger = logging.getLogger(__name__)

class CalculationEngine:
    """Implements the 11-step SIAT calculation logic for single workbook processing."""

    def __init__(self, drop_dump: pd.DataFrame, price_list: pd.DataFrame,
                 scheme_file: pd.DataFrame, sales_data: pd.DataFrame, brand: str = None,
                 purchase_price_threshold: Optional[float] = None,
                 price_variable_column: str = None,
                 lower_threshold: Optional[float] = None,
                 upper_threshold: Optional[float] = None):
        """
        Initialize with all required data sources from workbook.

        Args:
            drop_dump: DataFrame containing drop IMEIs and amounts
            price_list: DataFrame with pricing information
            scheme_file: DataFrame with scheme definitions
            sales_data: DataFrame with sales transactions
            brand: Selected brand name for brand-specific calculations
            purchase_price_threshold: Optional threshold for PCT Scheme-1 A/B selection (non-REDMI brands)
            price_variable_column: Price field to use in Final Price calculation (required)
            lower_threshold: Lower threshold for REDMI 3-tier logic
            upper_threshold: Upper threshold for REDMI 3-tier logic
        """
        self.drop_dump = drop_dump.copy()
        self.price_list = price_list.copy()
        self.scheme_file = scheme_file.copy()
        self.sales_data = sales_data.copy()
        self.brand = brand
        self.purchase_price_threshold = purchase_price_threshold
        self.price_variable_column = price_variable_column
        self.lower_threshold = lower_threshold
        self.upper_threshold = upper_threshold
        self.processed_data = None
        self.errors = []

        # Initialize separate fuzzy matching caches for price list and scheme
        self._price_model_cache = {}
        self._scheme_model_cache = {}
        
        # Check if PCT Scheme-5 and PCT Scheme-6 exist in scheme file
        self.has_pct_scheme_5 = 'Pct_Scheme_5' in self.scheme_file.columns
        self.has_pct_scheme_6 = 'Pct_Scheme_6' in self.scheme_file.columns
        
        if self.has_pct_scheme_5:
            logger.info("PCT Scheme-5 detected in scheme file")
        if self.has_pct_scheme_6:
            logger.info("PCT Scheme-6 detected in scheme file")
    
    def _get_column_case_insensitive(self, df: pd.DataFrame, column_name: str, default=None):
        """Get column value with case-insensitive matching.
        
        Args:
            df: DataFrame to search
            column_name: Column name to find (case-insensitive)
            default: Default value if column not found
            
        Returns:
            Column data if found, default otherwise
        """
        # First try exact match
        if column_name in df.columns:
            return df[column_name]
        
        # Try case-insensitive match
        column_name_lower = column_name.lower()
        for col in df.columns:
            if col.lower() == column_name_lower:
                return df[col]
        
        # Not found, return default
        return default

    def run_calculations(self) -> Tuple[pd.DataFrame, List[str]]:
        """
        Execute the complete 11-step calculation process.

        Returns:
            Tuple of (processed DataFrame, list of error messages)
        """
        logger.info("Starting SIAT calculation process...")

        # Pre-processing validation
        self._validate_input_data()

        # Additional safety checks
        if self.sales_data is None or self.price_list is None or self.scheme_file is None or self.drop_dump is None:
            raise ValueError("Data sources are None - check data loading")

        if not isinstance(self.sales_data, pd.DataFrame) or not isinstance(self.price_list, pd.DataFrame) or not isinstance(self.scheme_file, pd.DataFrame) or not isinstance(self.drop_dump, pd.DataFrame):
            raise ValueError("Data sources are not DataFrames - check data loading")

        try:
            # Start with sales data as the main dataframe
            df = self.sales_data.copy()
            logger.info(f"Initial data shape: {df.shape}")
            logger.info(f"Initial columns: {list(df.columns)[:10]}...")

            # Step 1-2: Drop Detection and Amount Application
            logger.info("Executing Step 1-2: Drop Detection")
            df = self._step_1_2_drop_detection(df)
            logger.info(f"After Step 1-2: {df.shape}")

            # Step 3-4: Price Match and Validation
            logger.info("Executing Step 3-4: Price Match")
            df = self._step_3_4_price_match(df)
            logger.info(f"After Step 3-4: {df.shape}")

            # Step 5-6: Tax Base Calculation
            logger.info("Executing Step 5-6: Tax Base")
            df = self._step_5_6_tax_base(df)
            logger.info(f"After Step 5-6: {df.shape}")

            # Step 7-8: Scheme Application
            logger.info("Executing Step 7-8: Scheme Application")
            df = self._step_7_8_scheme_application(df)
            logger.info(f"After Step 7-8: {df.shape}, columns: {len(df.columns)}")

            # Check if scheme columns were created
            scheme_cols = ['Total_Pct_Incentive', 'Total_Flat_Incentive']
            for col in scheme_cols:
                if col in df.columns:
                    logger.info(f"Scheme column {col} created: {df[col].sum()}")
                else:
                    logger.error(f"Scheme column {col} missing!")

            # Step 9: Incentive Sum
            logger.info("Executing Step 9: Incentive Sum")
            df = self._step_9_incentive_sum(df)
            logger.info(f"After Step 9: {df.shape}")

            if 'Total_Incentive_Received' in df.columns:
                logger.info(f"Total_Incentive_Received created: {df['Total_Incentive_Received'].sum()}")
            else:
                logger.error("Total_Incentive_Received column not created!")

            # Step 10: Net Landing Cost
            logger.info("Executing Step 10: NLC")
            df = self._step_10_nlc(df)
            logger.info(f"After Step 10: {df.shape}")

            # Step 11: Final validation and cleanup
            logger.info("Executing Step 11: Final Validation")
            df = self._step_11_final_validation(df)
            logger.info(f"After Step 11: {df.shape}")

            self.processed_data = df

            logger.info(f"SIAT calculation process completed successfully for {len(df)} records")
            return df, self.errors

        except Exception as e:
            error_msg = f"Critical error in calculation process: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Error type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.errors.append(error_msg)
            self.errors.append(f"Error details: {traceback.format_exc()}")
            return pd.DataFrame(), self.errors

    def _validate_input_data(self):
        """Validate input data before processing."""
        logger.info("Validating input data...")

        # Check sales data
        if self.sales_data.empty:
            raise ValueError("Sales data is empty")

        required_sales_cols = ['IMEI', 'Master_Model', 'Sell_Out_Date']
        missing_cols = [col for col in required_sales_cols if col not in self.sales_data.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns in sales data: {missing_cols}")

        # Check drop dump
        if self.drop_dump.empty:
            logger.warning("Drop dump is empty - no drop amounts will be applied")

        # # Check price list (OPTIONAL - COMMENTED OUT - NOT USED)
        # # Client provides all prices in Sales sheet, so Price List is not needed
        # if not self.price_list.empty:
        #     if 'Master_Model' not in self.price_list.columns:
        #         logger.warning("Price list missing 'Master_Model' column - price list will be ignored")
        #     if 'Purchase_Price' not in self.price_list.columns:
        #         logger.warning("Price list missing 'Purchase_Price' column - price list will be ignored")
        # else:
        #     logger.warning("Price list is empty - will be ignored")
        
        logger.info("Price list validation skipped - all prices come from Sales sheet")

        # Check scheme file
        if self.scheme_file.empty:
            logger.warning("Scheme file is empty - no incentives will be calculated")

        logger.info("Input data validation passed")
    
    def _step_1_2_drop_detection(self, df: pd.DataFrame) -> pd.DataFrame:
        """Step 1-2: Match IMEI in Drop Dump and apply drop amounts."""
        logger.info("Step 1-2: Performing drop detection and amount application...")

        # Create IMEI to drop amount mapping
        imei_drop_map = {}
        for _, row in self.drop_dump.iterrows():
            imei = str(row.get('IMEI', '')).strip()
            drop_amount = row.get('Drop_Amount', 0)
            if imei and pd.notna(drop_amount):
                imei_drop_map[imei] = float(drop_amount)

        # Apply drop amounts to sales data (use standardized column name)
        df['Drop_Amount'] = df['IMEI'].astype(str).str.strip().map(imei_drop_map).fillna(0)

        # Also add a boolean flag for drops
        df['Has_Drop'] = df['Drop_Amount'] > 0

        # Add 'drop' column for final output
        df['drop'] = df['Drop_Amount']

        drop_count = df['Has_Drop'].sum()
        total_drop_value = df['Drop_Amount'].sum()

        logger.info(f"Found {drop_count} drops with total value {total_drop_value:,.0f} out of {len(df)} records")
        return df
    
    def _step_3_4_price_match(self, df: pd.DataFrame) -> pd.DataFrame:
        """Step 3-4: Determine HIKE/DROP/SAME remarks.
        
        Step 3: MOP is provided by client in Sales sheet (no calculation needed)
        Step 4: Calculate HIKE = Current Month Invoice Price - Purchase Price
                Determine remark based on HIKE and DROP values
        
        NOTE: All prices including MOP come from Sales sheet - no calculations for MOP
        """
        logger.info("Step 3-4: Calculating HIKE and remarks...")

        # Check for "Not Active" in Sell_Out_Date before converting to datetime
        def check_sell_date_active(date_val):
            """Check if sell date is active or 'Not Active' string."""
            if pd.isna(date_val):
                return False  # Treat NaT/empty as Not Active
            
            # Check if it's a string containing "not active" (case-insensitive)
            if isinstance(date_val, str):
                if 'not active' in date_val.lower():
                    return False
            
            return True  # Valid date
        
        # Apply the check before datetime conversion
        df['Sell_Date_Active'] = df['Sell_Out_Date'].apply(check_sell_date_active)
        
        # Ensure Sell_Out_Date is datetime, convert invalid dates to NaT
        df['Sell_Out_Date'] = pd.to_datetime(df['Sell_Out_Date'], errors='coerce')
        
        # Update Sell_Date_Active for dates that failed to parse
        df.loc[df['Sell_Out_Date'].isna(), 'Sell_Date_Active'] = False
        
        # Log how many invalid/not active dates were found
        not_active_count = (~df['Sell_Date_Active']).sum()
        if not_active_count > 0:
            logger.warning(f"Found {not_active_count} 'Not Active' or invalid sell out dates")
            self.errors.append(f"Warning: {not_active_count} records have 'Not Active' or invalid sell out dates")

        # Step 3: MOP is provided by client in Sales sheet - no calculation needed
        # Client provides "MOP at the Time of Purchase" directly in input
        # We just use it as-is from the Sales sheet
        if 'Purchase_Price' in df.columns:
            # Use Purchase_Price as Matched_Price for compatibility
            # (MOP should already be in the Sales sheet as a separate column)
            df['Matched_Price'] = df.get('Purchase_Price', 0)
        else:
            df['Matched_Price'] = 0
            logger.warning("Purchase_Price not found, setting Matched_Price to 0")

        # Step 4: Calculate HIKE = Current Month Invoice Price - Purchase Price
        def get_hike_remark(row):
            purchase = row.get('Purchase_Price', 0) or 0
            current_month_invoice = row.get('Current_Month_Invoice_Price', 0)
            drop = row.get('Drop_Amount', 0) or 0
            
            # If current_month_invoice is NaN or None, treat as 0
            if pd.isna(current_month_invoice):
                current_month_invoice = 0
            
            # HIKE = Current Month Invoice Price - Purchase Price
            hike_value = current_month_invoice - purchase
            
            # Round to 2 decimal places for comparison
            hike_value = round(hike_value, 2)
            drop = round(drop, 2)
            
            # If HIKE is negative, set to 0 (no hike)
            if hike_value < 0:
                hike_value = 0
            
            # Remark logic: 
            # If drop == 0 AND hike == 0, show "same"
            if drop == 0 and hike_value == 0:
                remark = 'same'
            elif drop > 0 and hike_value > 0:
                remark = 'drop and hike both'
            elif drop > 0:
                remark = 'drop'
            elif hike_value > 0:
                remark = 'hike'
            else:
                remark = 'same'
            
            return pd.Series({'Calc_HIKE': hike_value, 'Calc_Remark': remark})

        hike_remark = df.apply(get_hike_remark, axis=1)
        df['Calc_HIKE'] = hike_remark['Calc_HIKE']
        df['Calc_Remark'] = hike_remark['Calc_Remark']

        logger.info(f"HIKE and remarks calculated for {len(df)} records")
        return df
    
    def _step_5_6_tax_base(self, df: pd.DataFrame) -> pd.DataFrame:
        """Step 5-6: Calculate Final Price and Pre-GST Price with brand-specific logic."""
        logger.info("Step 5-6: Calculating tax base...")

        # Validate that price_variable_column is provided
        if not self.price_variable_column or self.price_variable_column == "-- Select Price Variable --":
            raise ValueError("Price variable column must be selected for Final Price calculation")

        # Ensure required columns exist
        if 'Purchase_Price' not in df.columns:
            logger.warning("Purchase_Price column missing, using 0 as fallback")
            df['Purchase_Price'] = 0

        if 'Drop_Amount' not in df.columns:
            logger.warning("Drop_Amount column missing, assuming 0")
            df['Drop_Amount'] = 0
            
        if 'Current_Month_Invoice_Price' not in df.columns:
            logger.warning("Current_Month_Invoice_Price column missing, assuming 0")
            df['Current_Month_Invoice_Price'] = 0

        # Map user-selected price variable to actual column name
        price_column_mapping = {
            "Current Month Invoice Price": "Current_Month_Invoice_Price",
            "Purchase Price": "Purchase_Price",
            "Current MOP/SRP": "Current_MOP_SRP"  # Use standardized name
        }
        
        # Get the actual column name based on user selection
        selected_column = price_column_mapping.get(self.price_variable_column)
        
        if not selected_column:
            raise ValueError(f"Invalid price variable selection: {self.price_variable_column}")
        
        # Ensure the selected column exists (case-insensitive check)
        if selected_column not in df.columns:
            # Try case-insensitive search
            found = False
            for col in df.columns:
                if col.lower() == selected_column.lower():
                    selected_column = col
                    found = True
                    break
            
            if not found:
                raise ValueError(f"{selected_column} column not found in sales data. Available columns: {list(df.columns)}")

        # Get the price variable value for each row
        price_variable = df[selected_column].fillna(0)

        # Brand-specific Final Price calculation with dynamic price variable
        brand_upper = self.brand.upper() if self.brand else ""
        
        logger.info(f"Applying brand-specific calculation for: {brand_upper}")
        logger.info(f"Using price variable: {self.price_variable_column} (column: {selected_column})")
        
        if brand_upper == "REDMI":
            # REDMI: FINAL PRICE = {price_variable} (Drop is NOT deducted)
            df['Tax_Base_Final_Price'] = price_variable
            logger.info(f"Applied REDMI formula: {self.price_variable_column} (Drop NOT deducted)")
            
        elif brand_upper == "SAMSUNG":
            # SAMSUNG: FINAL PRICE = {price_variable} - FLAT PAYOUT (Drop is NOT deducted)
            # Note: Flat payout will be calculated later, so we'll adjust this in step 10
            df['Tax_Base_Final_Price'] = price_variable  # No Drop deduction for Samsung
            df['Samsung_Adjustment_Needed'] = True  # Flag for later adjustment
            logger.info(f"Applied SAMSUNG formula: {self.price_variable_column} (Flat Payout will be deducted later, Drop NOT deducted)")
            
        elif brand_upper in ["REALME", "OPPO"]:
            # REALME/OPPO: FINAL PRICE = {price_variable} - DROP
            df['Tax_Base_Final_Price'] = price_variable - df['Drop_Amount']
            logger.info(f"Applied {brand_upper} formula: {self.price_variable_column} - Drop")
            
        else:
            # Default for other brands: {price_variable} - DROP
            df['Tax_Base_Final_Price'] = price_variable - df['Drop_Amount']
            logger.info(f"Applied default formula: {self.price_variable_column} - Drop")

        # Pre-GST Price = Final Price / 1.18
        df['Tax_Base_Pre_GST_Price'] = df['Tax_Base_Final_Price'] / 1.18

        # For compatibility, also set standard names
        df['Final_Price'] = df['Tax_Base_Final_Price']
        df['Pre_GST_Price'] = df['Tax_Base_Pre_GST_Price']

        return df
    
    def _step_7_8_scheme_application(self, df: pd.DataFrame) -> pd.DataFrame:
        """Step 7-8: Apply schemes based on Master Model and Sell Out Date."""
        logger.info("Step 7-8: Applying schemes...")
        logger.info(f"Scheme file columns: {list(self.scheme_file.columns)}")

        # Check if required columns exist
        if 'Scheme_Start_Date' not in self.scheme_file.columns:
            logger.error(f"Scheme_Start_Date not found. Available columns: {list(self.scheme_file.columns)}")
            raise ValueError(f"Scheme file missing 'Scheme_Start_Date' column. Available: {list(self.scheme_file.columns)}")
        
        if 'Scheme_End_Date' not in self.scheme_file.columns:
            logger.error(f"Scheme_End_Date not found. Available columns: {list(self.scheme_file.columns)}")
            raise ValueError(f"Scheme file missing 'Scheme_End_Date' column. Available: {list(self.scheme_file.columns)}")

        # Ensure scheme dates are datetime, filter out invalid dates
        self.scheme_file['Scheme_Start_Date'] = pd.to_datetime(self.scheme_file['Scheme_Start_Date'], errors='coerce')
        self.scheme_file['Scheme_End_Date'] = pd.to_datetime(self.scheme_file['Scheme_End_Date'], errors='coerce')
        
        # Check if Flat Payout date columns exist
        has_flat_dates = 'Flat_Payout_Start_Date' in self.scheme_file.columns and 'Flat_Payout_End_Date' in self.scheme_file.columns
        
        if has_flat_dates:
            self.scheme_file['Flat_Payout_Start_Date'] = pd.to_datetime(self.scheme_file['Flat_Payout_Start_Date'], errors='coerce')
            self.scheme_file['Flat_Payout_End_Date'] = pd.to_datetime(self.scheme_file['Flat_Payout_End_Date'], errors='coerce')
            logger.info("Flat Payout date range columns detected and parsed")
        
        # Remove rows with invalid dates
        valid_scheme_rows = self.scheme_file[
            self.scheme_file['Scheme_Start_Date'].notna() & 
            self.scheme_file['Scheme_End_Date'].notna()
        ]
        
        invalid_count = len(self.scheme_file) - len(valid_scheme_rows)
        if invalid_count > 0:
            logger.warning(f"Removed {invalid_count} scheme rows with invalid dates")
            self.errors.append(f"Warning: {invalid_count} scheme rows had invalid dates and were skipped")
        
        self.scheme_file = valid_scheme_rows
        
        if self.scheme_file.empty:
            logger.warning("No valid scheme data available after date filtering")
            # Return zero schemes for all rows
            df['pct_scheme_1'] = 0
            df['pct_scheme_2'] = 0
            df['pct_scheme_3'] = 0
            df['pct_scheme_4'] = 0
            df['Pct_Incentive_1'] = 0
            df['Pct_Incentive_2'] = 0
            df['Pct_Incentive_3'] = 0
            df['Pct_Incentive_4'] = 0
            if self.has_pct_scheme_5:
                df['pct_scheme_5'] = 0
                df['Pct_Incentive_5'] = 0
            if self.has_pct_scheme_6:
                df['pct_scheme_6'] = 0
                df['Pct_Incentive_6'] = 0
            df['Flat_Incentive'] = 0
            df['Total_Pct_Incentive'] = 0
            df['Total_Flat_Incentive'] = 0
            return df

        def apply_scheme(row):
            master_model = str(row.get('Master_Model', '') or '')
            sell_date = row['Sell_Out_Date']
            pre_gst_price = row.get('Tax_Base_Pre_GST_Price', 0) or 0
            final_price = row.get('Tax_Base_Final_Price', 0) or 0
            sell_date_active = row.get('Sell_Date_Active', True)
            purchase_price = row.get('Purchase_Price', 0) or 0
            
            # Determine brand
            brand_upper = self.brand.upper() if self.brand else ""
            
            # For REDMI and SAMSUNG, use Current MOP/SRP for threshold comparison
            # For other brands, use Purchase Price
            if brand_upper in ["REDMI", "SAMSUNG"]:
                threshold_comparison_price = row.get('Current_MOP_SRP', 0) or 0
            else:
                threshold_comparison_price = purchase_price
            
            # For REDMI, use FINAL PRICE FOR CALCULATION for scheme amount calculation
            # For other brands, use PRE GST OF FINAL PRICE CALCULATION
            if brand_upper == "REDMI":
                scheme_calculation_base = final_price
            else:
                scheme_calculation_base = pre_gst_price

            zero = pd.Series({
                'pct_scheme_1': 0, 'pct_scheme_2': 0, 'pct_scheme_3': 0, 'pct_scheme_4': 0,
                'Pct_Incentive_1': 0, 'Pct_Incentive_2': 0, 'Pct_Incentive_3': 0, 'Pct_Incentive_4': 0,
                'Flat_Incentive': 0, 'Total_Pct_Incentive': 0, 'Total_Flat_Incentive': 0
            })
            
            # Add PCT Scheme-5 and 6 if they exist
            if self.has_pct_scheme_5:
                zero['pct_scheme_5'] = 0
                zero['Pct_Incentive_5'] = 0
            if self.has_pct_scheme_6:
                zero['pct_scheme_6'] = 0
                zero['Pct_Incentive_6'] = 0

            # Check if master model exists
            if not master_model:
                return zero
            
            # If Sell_Out_Date is "Not Active" or invalid, skip ALL schemes
            if not sell_date_active:
                return zero

            # Use cached fuzzy match against scheme file
            if master_model not in self._scheme_model_cache:
                best_match = self._fuzzy_match_model(
                    str(master_model),
                    self.scheme_file['Master_Model'].dropna().astype(str).tolist()
                )
                self._scheme_model_cache[master_model] = best_match

            best_match = self._scheme_model_cache[master_model]

            if not best_match:
                return zero

            # Normal case: Use Scheme_Start_Date and Scheme_End_Date for filtering
            if pd.isna(sell_date) or isinstance(sell_date, str):
                return zero
            
            pct_mask = (
                (self.scheme_file['Master_Model'].astype(str) == best_match[0]) &
                (self.scheme_file['Scheme_Start_Date'] <= sell_date) &
                (self.scheme_file['Scheme_End_Date'] >= sell_date)
            )
            applicable_pct_schemes = self.scheme_file[pct_mask]

            # Initialize aggregated values
            pct_scheme_1 = pct_scheme_2 = pct_scheme_3 = pct_scheme_4 = pct_scheme_5 = pct_scheme_6 = 0
            pct_scheme_1_calc = pct_scheme_2_calc = pct_scheme_3_calc = pct_scheme_4_calc = pct_scheme_5_calc = pct_scheme_6_calc = 0
            flat_scheme = 0

            # Loop through ALL matching PCT scheme entries and aggregate
            if not applicable_pct_schemes.empty:
                # Log if multiple schemes are being aggregated
                if len(applicable_pct_schemes) > 1:
                    logger.info(f"DEBUG - Multiple scheme entries found for {master_model}: {len(applicable_pct_schemes)} rows will be aggregated")
                
                for idx, (_, scheme) in enumerate(applicable_pct_schemes.iterrows(), 1):
                    # Log scheme values being processed
                    logger.info(f"DEBUG - Processing scheme row {idx} for {master_model}: PCT-1={scheme.get('Pct_Scheme_1', 0)}, PCT-2={scheme.get('Pct_Scheme_2', 0)}, PCT-3={scheme.get('Pct_Scheme_3', 0)}, PCT-4={scheme.get('Pct_Scheme_4', 0)}")
                    
                    # ===== PCT SCHEME-1 LOGIC =====
                    condition_1 = str(scheme.get('Condition_1', '')).strip().lower()
                    has_price_slab = condition_1 in ['price slab', 'priceslab', 'price_slab']
                    
                    # Check if A/B/C columns exist
                    has_a_col = 'Pct_Scheme_1_A' in self.scheme_file.columns
                    has_b_col = 'Pct_Scheme_1_B' in self.scheme_file.columns
                    has_c_col = 'Pct_Scheme_1_C' in self.scheme_file.columns
                    
                    # Get PCT Scheme-1 value based on brand and conditions
                    if brand_upper == "REDMI" and has_price_slab and has_a_col and has_b_col and has_c_col:
                        # REDMI 3-tier logic with CONDITION-1 = "PRICE SLAB"
                        # Use Current MOP/SRP for threshold comparison
                        if self.lower_threshold is not None and self.upper_threshold is not None:
                            if threshold_comparison_price < self.lower_threshold:
                                pct_scheme_1_raw = scheme.get('Pct_Scheme_1_A', 0) or 0
                            elif threshold_comparison_price <= self.upper_threshold:
                                pct_scheme_1_raw = scheme.get('Pct_Scheme_1_B', 0) or 0
                            else:  # threshold_comparison_price > upper_threshold
                                pct_scheme_1_raw = scheme.get('Pct_Scheme_1_C', 0) or 0
                        else:
                            # Thresholds not provided - default to A
                            pct_scheme_1_raw = scheme.get('Pct_Scheme_1_A', 0) or 0
                    
                    elif has_price_slab and has_a_col and has_b_col:
                        # Non-REDMI 2-tier logic with CONDITION-1 = "PRICE SLAB"
                        # SAMSUNG uses Current MOP/SRP, others use Purchase Price
                        if self.purchase_price_threshold is not None:
                            if threshold_comparison_price <= self.purchase_price_threshold:
                                pct_scheme_1_raw = scheme.get('Pct_Scheme_1_A', 0) or 0
                            else:
                                pct_scheme_1_raw = scheme.get('Pct_Scheme_1_B', 0) or 0
                        else:
                            # Threshold not provided - default to A
                            pct_scheme_1_raw = scheme.get('Pct_Scheme_1_A', 0) or 0
                    
                    elif has_a_col:
                        # CONDITION-1 != "PRICE SLAB" or missing - always use A if exists
                        pct_scheme_1_raw = scheme.get('Pct_Scheme_1_A', 0) or 0
                    else:
                        # No A/B columns - use original PCT Scheme-1
                        pct_scheme_1_raw = scheme.get('Pct_Scheme_1', 0) or 0
                    
                    # ===== PCT SCHEME-2 LOGIC =====
                    # Check CONDITION-2 for REDMI
                    condition_2 = str(scheme.get('Condition_2', '')).strip().upper()
                    has_condition_2_above = 'ABOVE' in condition_2
                    has_2a_col = 'Pct_Scheme_2_A' in self.scheme_file.columns
                    
                    if brand_upper == "REDMI" and has_condition_2_above and has_2a_col:
                        # REDMI CONDITION-2 logic
                        # Use Current MOP/SRP for threshold comparison
                        if self.lower_threshold is not None and threshold_comparison_price > self.lower_threshold:
                            pct_scheme_2_raw = scheme.get('Pct_Scheme_2_A', 0) or 0
                        else:
                            pct_scheme_2_raw = 0
                    else:
                        # Non-REDMI or no CONDITION-2: Use regular Pct_Scheme_2
                        pct_scheme_2_raw = scheme.get('Pct_Scheme_2', 0) or 0
                    
                    # Get other scheme values
                    pct_scheme_3_raw = scheme.get('Pct_Scheme_3', 0) or 0
                    pct_scheme_4_raw = scheme.get('Pct_Scheme_4', 0) or 0
                    pct_scheme_5_raw = scheme.get('Pct_Scheme_5', 0) or 0 if self.has_pct_scheme_5 else 0
                    pct_scheme_6_raw = scheme.get('Pct_Scheme_6', 0) or 0 if self.has_pct_scheme_6 else 0
                    
                    # Convert to percentage format and calculation format
                    # PCT Scheme-1
                    if pct_scheme_1_raw > 0 and pct_scheme_1_raw < 1:
                        pct_scheme_1 += pct_scheme_1_raw * 100
                        pct_scheme_1_calc += pct_scheme_1_raw
                    else:
                        pct_scheme_1 += pct_scheme_1_raw
                        pct_scheme_1_calc += pct_scheme_1_raw / 100 if pct_scheme_1_raw > 0 else 0
                    
                    # PCT Scheme-2
                    if pct_scheme_2_raw > 0 and pct_scheme_2_raw < 1:
                        pct_scheme_2 += pct_scheme_2_raw * 100
                        pct_scheme_2_calc += pct_scheme_2_raw
                    else:
                        pct_scheme_2 += pct_scheme_2_raw
                        pct_scheme_2_calc += pct_scheme_2_raw / 100 if pct_scheme_2_raw > 0 else 0
                    
                    # PCT Scheme-3
                    if pct_scheme_3_raw > 0 and pct_scheme_3_raw < 1:
                        pct_scheme_3 += pct_scheme_3_raw * 100
                        pct_scheme_3_calc += pct_scheme_3_raw
                    else:
                        pct_scheme_3 += pct_scheme_3_raw
                        pct_scheme_3_calc += pct_scheme_3_raw / 100 if pct_scheme_3_raw > 0 else 0
                    
                    # PCT Scheme-4
                    if pct_scheme_4_raw > 0 and pct_scheme_4_raw < 1:
                        pct_scheme_4 += pct_scheme_4_raw * 100
                        pct_scheme_4_calc += pct_scheme_4_raw
                    else:
                        pct_scheme_4 += pct_scheme_4_raw
                        pct_scheme_4_calc += pct_scheme_4_raw / 100 if pct_scheme_4_raw > 0 else 0
                    
                    # PCT Scheme-5 (if exists)
                    if self.has_pct_scheme_5:
                        if pct_scheme_5_raw > 0 and pct_scheme_5_raw < 1:
                            pct_scheme_5 += pct_scheme_5_raw * 100
                            pct_scheme_5_calc += pct_scheme_5_raw
                        else:
                            pct_scheme_5 += pct_scheme_5_raw
                            pct_scheme_5_calc += pct_scheme_5_raw / 100 if pct_scheme_5_raw > 0 else 0
                    
                    # PCT Scheme-6 (if exists)
                    if self.has_pct_scheme_6:
                        if pct_scheme_6_raw > 0 and pct_scheme_6_raw < 1:
                            pct_scheme_6 += pct_scheme_6_raw * 100
                            pct_scheme_6_calc += pct_scheme_6_raw
                        else:
                            pct_scheme_6 += pct_scheme_6_raw
                            pct_scheme_6_calc += pct_scheme_6_raw / 100 if pct_scheme_6_raw > 0 else 0

            # For Flat Payout: Apply when sell_date is valid
            if not (pd.isna(sell_date) or isinstance(sell_date, str)):
                if has_flat_dates:
                    # Check if this specific scheme row has Flat Payout dates populated
                    # We need to check each scheme row individually
                    for _, scheme in self.scheme_file[self.scheme_file['Master_Model'].astype(str) == best_match[0]].iterrows():
                        flat_start = scheme.get('Flat_Payout_Start_Date')
                        flat_end = scheme.get('Flat_Payout_End_Date')
                        _flat = scheme.get('Flat_Scheme', None)
                        
                        # DEBUG: Log the comparison
                        if pd.notna(_flat) and _flat != 0:
                            logger.info(f"DEBUG - Model: {master_model}, Sell Date: {sell_date}, Flat Start: {flat_start}, Flat End: {flat_end}, Flat Value: {_flat}")
                        
                        # Skip if no flat scheme value
                        if pd.isna(_flat) or _flat == 0:
                            continue
                        
                        # If Flat dates are populated, use them ONLY (no fallback)
                        if pd.notna(flat_start) and pd.notna(flat_end):
                            if flat_start <= sell_date <= flat_end:
                                logger.info(f"DEBUG - MATCH: Applying Flat Payout {_flat} (within range)")
                                flat_scheme += float(_flat)
                            else:
                                logger.info(f"DEBUG - NO MATCH: Sell date {sell_date} is outside Flat range {flat_start} to {flat_end}")
                        # If Flat dates are empty, fall back to Scheme dates
                        elif pd.isna(flat_start) and pd.isna(flat_end):
                            scheme_start = scheme.get('Scheme_Start_Date')
                            scheme_end = scheme.get('Scheme_End_Date')
                            if pd.notna(scheme_start) and pd.notna(scheme_end):
                                if scheme_start <= sell_date <= scheme_end:
                                    logger.info(f"DEBUG - FALLBACK: Applying Flat Payout {_flat} (using Scheme dates)")
                                    flat_scheme += float(_flat)
                        else:
                            # One date is populated, one is not - this is an error condition
                            logger.warning(f"DEBUG - ERROR: Flat dates partially populated for {master_model}")
                else:
                    # No Flat Payout date columns, use Scheme dates
                    flat_mask = (
                        (self.scheme_file['Master_Model'].astype(str) == best_match[0]) &
                        (self.scheme_file['Scheme_Start_Date'] <= sell_date) &
                        (self.scheme_file['Scheme_End_Date'] >= sell_date)
                    )
                    applicable_flat_schemes = self.scheme_file[flat_mask]
                    
                    # Aggregate Flat Scheme values
                    if not applicable_flat_schemes.empty:
                        for _, scheme in applicable_flat_schemes.iterrows():
                            _flat = scheme.get('Flat_Scheme', None)
                            flat_scheme_entry = float(_flat) if pd.notna(_flat) else 0
                            flat_scheme += flat_scheme_entry

            # Step 8: pct amount = pct_scheme_calc * scheme_calculation_base
            # For REDMI: scheme_calculation_base = FINAL PRICE FOR CALCULATION
            # For others: scheme_calculation_base = PRE GST OF FINAL PRICE CALCULATION
            pct_incentive_1 = pct_scheme_1_calc * scheme_calculation_base
            pct_incentive_2 = pct_scheme_2_calc * scheme_calculation_base
            pct_incentive_3 = pct_scheme_3_calc * scheme_calculation_base
            pct_incentive_4 = pct_scheme_4_calc * scheme_calculation_base
            pct_incentive_5 = pct_scheme_5_calc * scheme_calculation_base if self.has_pct_scheme_5 else 0
            pct_incentive_6 = pct_scheme_6_calc * scheme_calculation_base if self.has_pct_scheme_6 else 0
            total_pct = pct_incentive_1 + pct_incentive_2 + pct_incentive_3 + pct_incentive_4 + pct_incentive_5 + pct_incentive_6

            result = {
                'pct_scheme_1': pct_scheme_1,  # Store as percentage (e.g., 2.5)
                'pct_scheme_2': pct_scheme_2,
                'pct_scheme_3': pct_scheme_3,
                'pct_scheme_4': pct_scheme_4,
                'Pct_Incentive_1': pct_incentive_1,
                'Pct_Incentive_2': pct_incentive_2,
                'Pct_Incentive_3': pct_incentive_3,
                'Pct_Incentive_4': pct_incentive_4,
                'Flat_Incentive': flat_scheme,
                'Total_Pct_Incentive': total_pct,
                'Total_Flat_Incentive': flat_scheme
            }
            
            # Add PCT Scheme-5 and 6 if they exist
            if self.has_pct_scheme_5:
                result['pct_scheme_5'] = pct_scheme_5
                result['Pct_Incentive_5'] = pct_incentive_5
            if self.has_pct_scheme_6:
                result['pct_scheme_6'] = pct_scheme_6
                result['Pct_Incentive_6'] = pct_incentive_6
            
            return pd.Series(result)

        # Apply scheme calculations
        scheme_results = df.apply(apply_scheme, axis=1)
        df = pd.concat([df, scheme_results], axis=1)

        total_schemes = (df['Total_Pct_Incentive'] + df['Total_Flat_Incentive']).sum()
        logger.info(f"Applied schemes with total incentive value {total_schemes:,.0f}")
        return df
    
    def _step_9_incentive_sum(self, df: pd.DataFrame) -> pd.DataFrame:
        """Step 9: Aggregate all incentives into Total Incentive Received."""
        logger.info("Step 9: Calculating total incentives...")

        # Ensure required columns exist, create them if missing
        if 'Total_Pct_Incentive' not in df.columns:
            logger.warning("Total_Pct_Incentive column missing, creating with default values")
            df['Total_Pct_Incentive'] = 0

        if 'Total_Flat_Incentive' not in df.columns:
            logger.warning("Total_Flat_Incentive column missing, creating with default values")
            df['Total_Flat_Incentive'] = 0

        df['Total_Incentive_Received'] = df['Total_Pct_Incentive'] + df['Total_Flat_Incentive']
        logger.info(f"Total incentives calculated: {df['Total_Incentive_Received'].sum():,.0f}")

        return df

    def _step_10_nlc(self, df: pd.DataFrame) -> pd.DataFrame:
        """Step 10: Calculate Net Landing Cost (NLC) with Samsung adjustment."""
        logger.info("Step 10: Calculating Net Landing Cost...")

        # Ensure required columns exist
        if 'Purchase_Price' not in df.columns:
            logger.warning("Purchase_Price column missing, using 0 as fallback")
            df['Purchase_Price'] = 0

        if 'Drop_Amount' not in df.columns:
            logger.warning("Drop_Amount column missing, assuming 0")
            df['Drop_Amount'] = 0

        if 'Total_Incentive_Received' not in df.columns:
            logger.warning("Total_Incentive_Received column missing, assuming 0")
            df['Total_Incentive_Received'] = 0
            
        if 'Flat_Incentive' not in df.columns:
            logger.warning("Flat_Incentive column missing, assuming 0")
            df['Flat_Incentive'] = 0

        # Samsung-specific adjustment: Subtract Flat Payout from Final Price
        brand_upper = self.brand.upper() if self.brand else ""
        if brand_upper == "SAMSUNG" and 'Samsung_Adjustment_Needed' in df.columns:
            df['Tax_Base_Final_Price'] = df['Tax_Base_Final_Price'] - df['Flat_Incentive']
            df['Final_Price'] = df['Tax_Base_Final_Price']
            # Recalculate Pre-GST Price after adjustment
            df['Tax_Base_Pre_GST_Price'] = df['Tax_Base_Final_Price'] / 1.18
            df['Pre_GST_Price'] = df['Tax_Base_Pre_GST_Price']
            logger.info("Applied Samsung adjustment: Subtracted Flat Payout from Final Price")

        # Store final price for calculations
        df['Calculated_Final_Price'] = df['Tax_Base_Final_Price']

        # NLC = Final Price - Total Incentive Received
        df['Calculated_NLC'] = df['Calculated_Final_Price'] - df['Total_Incentive_Received']

        # Calculate margin (using purchase price as base)
        df['Calculated_Margin'] = df['Purchase_Price'] - df['Calculated_NLC']

        # For backward compatibility, also set the standard column names
        df['Final_Price'] = df['Calculated_Final_Price']
        df['NLC'] = df['Calculated_NLC']
        df['Margin'] = df['Calculated_Margin']

        logger.info(f"NLC calculations completed. Total NLC: {df['Calculated_NLC'].sum():,.0f}")
        return df

    def _step_11_final_validation(self, df: pd.DataFrame) -> pd.DataFrame:
        """Step 11: Final validation and cleanup."""
        logger.info("Step 11: Performing final validation...")

        # Validate date consistency
        if 'Purchase_Date' in df.columns:
            # Parse dates with explicit DD-MM-YYYY format (dayfirst=True)
            df['Purchase_Date'] = pd.to_datetime(df['Purchase_Date'], errors='coerce', dayfirst=True)
            df['Sell_Out_Date'] = pd.to_datetime(df['Sell_Out_Date'], errors='coerce', dayfirst=True)
            
            invalid_dates = df[
                (df['Purchase_Date'].notna()) &
                (df['Sell_Out_Date'].notna()) &
                (df['Sell_Out_Date'] < df['Purchase_Date'])
            ]
            if not invalid_dates.empty:
                self.errors.append(f"Found {len(invalid_dates)} records where Sell Out Date is before Purchase Date")

        # Check for missing critical data
        missing_prices = df['Matched_Price'].isna().sum()
        if missing_prices > 0:
            self.errors.append(f"Warning: {missing_prices} records have missing matched prices")

        missing_models = df['Master_Model'].isna().sum()
        if missing_models > 0:
            self.errors.append(f"Warning: {missing_models} records have missing Master Model")

        # Define final column order with display names (base columns)
        final_columns = [
            'IMEI',
            'Sell Out Date',
            'Master Model',
            'SERIES',
            'Distributor',
            'Purchase Date',
            'Purchase Price',
            'Current Month Invoice Price',
            'Current Month Pre-GST of Invoice Price',
            'Current MOP/SRP',
            'Activation Date',
            'MOP at the Time of Purchase',
            'Drop',
            'Flat Payout',
            'HIKE',
            'Remark (Drop, Hike, Same (Drop and Hike Both)',
            'FINAL PRICE FOR CALCULATION',
            'PRE GST OF FINAL PRICE CALCULATION',
            'PCT Scheme-1',
            'Amount PCT Scheme-1',
            'PCT Scheme-2',
            'Amount PCT Scheme-2',
            'PCT Scheme-3',
            'Amount PCT Scheme-3',
            'PCT Scheme-4',
            'Amount PCT Scheme-4',
        ]
        
        # Dynamically add PCT Scheme-5 and 6 if they exist
        # Check if the calculation engine has these schemes
        has_scheme_5 = hasattr(self, 'has_pct_scheme_5') and self.has_pct_scheme_5
        has_scheme_6 = hasattr(self, 'has_pct_scheme_6') and self.has_pct_scheme_6
        
        if has_scheme_5:
            final_columns.extend(['PCT Scheme-5', 'Amount PCT Scheme-5'])
        if has_scheme_6:
            final_columns.extend(['PCT Scheme-6', 'Amount PCT Scheme-6'])
        
        # Add final columns
        final_columns.extend([
            'Total Scheme Received',
            'TOTAL PCT SCHEME + FLAT PAYOUT'
        ])

        # Create final dataframe with renamed columns
        final_df = pd.DataFrame()
        
        # Map internal columns to display columns
        final_df['IMEI'] = df['IMEI'].astype(str).str.replace(',', '', regex=False)
        final_df['Sell Out Date'] = df.get('Sell_Out_Date', '')
        final_df['Master Model'] = df.get('Master_Model', '')
        
        # SERIES: use original value from input only - no auto-extraction
        # Client is responsible for providing SERIES data
        final_df['SERIES'] = df.get('SERIES', '')
        
        final_df['Distributor'] = df.get('Distributor', '')
        final_df['Purchase Date'] = df.get('Purchase_Date', '')
        final_df['Purchase Price'] = df.get('Purchase_Price', np.nan).fillna(0).round(0).astype('Int64')
        final_df['Current Month Invoice Price'] = df.get('Current_Month_Invoice_Price', np.nan).fillna(0).round(0).astype('Int64')
        final_df['Current Month Pre-GST of Invoice Price'] = df.get('Current_Month_Pre_GST_Invoice_Price', np.nan).fillna(0).round(0).astype('Int64')
        final_df['Current MOP/SRP'] = df.get('Current_MOP_SRP', np.nan).fillna(0).round(0).astype('Int64')
        final_df['Activation Date'] = df.get('Activation_Date', np.nan)
        final_df['MOP at the Time of Purchase'] = df.get('Matched_Price', np.nan).fillna(0).round(0).astype('Int64')
        final_df['Drop'] = df.get('Drop_Amount', 0).fillna(0).round(0).astype('Int64')
        final_df['Flat Payout'] = df.get('Flat_Incentive', 0).fillna(0).round(0).astype('Int64')
        final_df['HIKE'] = df.get('Calc_HIKE', np.nan).fillna(0).round(0).astype('Int64')
        final_df['Remark (Drop, Hike, Same (Drop and Hike Both)'] = df.get('Calc_Remark', '')
        final_df['FINAL PRICE FOR CALCULATION'] = df.get('Tax_Base_Final_Price', np.nan).fillna(0).round(0).astype('Int64')
        final_df['PRE GST OF FINAL PRICE CALCULATION'] = df.get('Tax_Base_Pre_GST_Price', np.nan).fillna(0).round(0).astype('Int64')
        
        # PCT Schemes with percentage formatting
        final_df['PCT Scheme-1'] = df.get('pct_scheme_1', 0)
        final_df['Amount PCT Scheme-1'] = df.get('Pct_Incentive_1', 0).fillna(0).round(0).astype('Int64')
        final_df['PCT Scheme-2'] = df.get('pct_scheme_2', 0)
        final_df['Amount PCT Scheme-2'] = df.get('Pct_Incentive_2', 0).fillna(0).round(0).astype('Int64')
        final_df['PCT Scheme-3'] = df.get('pct_scheme_3', 0)
        final_df['Amount PCT Scheme-3'] = df.get('Pct_Incentive_3', 0).fillna(0).round(0).astype('Int64')
        final_df['PCT Scheme-4'] = df.get('pct_scheme_4', 0)
        final_df['Amount PCT Scheme-4'] = df.get('Pct_Incentive_4', 0).fillna(0).round(0).astype('Int64')
        
        # Dynamically add PCT Scheme-5 and 6 if they exist
        if has_scheme_5:
            final_df['PCT Scheme-5'] = df.get('pct_scheme_5', 0)
            final_df['Amount PCT Scheme-5'] = df.get('Pct_Incentive_5', 0).fillna(0).round(0).astype('Int64')
        
        if has_scheme_6:
            final_df['PCT Scheme-6'] = df.get('pct_scheme_6', 0)
            final_df['Amount PCT Scheme-6'] = df.get('Pct_Incentive_6', 0).fillna(0).round(0).astype('Int64')
        
        # Format percentage columns to show with % symbol
        pct_columns = ['PCT Scheme-1', 'PCT Scheme-2', 'PCT Scheme-3', 'PCT Scheme-4']
        if has_scheme_5:
            pct_columns.append('PCT Scheme-5')
        if has_scheme_6:
            pct_columns.append('PCT Scheme-6')
        
        for col in pct_columns:
            if col in final_df.columns:
                final_df[col] = final_df[col].apply(lambda x: f"{round(x, 2)}%" if pd.notna(x) and x > 0 else ("0%" if pd.notna(x) else ""))
        
        final_df['Total Scheme Received'] = df.get('Total_Incentive_Received', 0).fillna(0).round(0).astype('Int64')
        final_df['TOTAL PCT SCHEME + FLAT PAYOUT'] = df.get('Calculated_NLC', np.nan).fillna(0).round(0).astype('Int64')

        # Keep only columns that have data
        final_df = final_df[final_columns]

        logger.info(f"Final validation completed. Shape: {final_df.shape}")
        return final_df

    def _get_default_value_for_column(self, column_name: str, df: pd.DataFrame):
        """Get default value for columns that don't exist in current data."""
        if column_name == 'SERIES':
            # Try to extract series from master model (e.g., "REALME" from "REALME C71 4@64")
            if 'master model' in df.columns:
                return df['master model'].str.split().str[0]
            elif 'Master_Model' in df.columns:
                return df['Master_Model'].str.split().str[0]
            return ''

        elif column_name == 'MOP AT THE TIME OF PURCHASE':
            # This is the matched price from the price list
            return df.get('Matched_Price', df.get('Purchase_Price', 0))

        elif 'hike' in column_name.lower() and 'validation' in column_name.lower():
            # Complex hike logic based on date validation
            # For now, return 0 - this needs to be implemented based on business rules
            return 0

        elif column_name == 'HIKE':
            # Calculated hike value (absolute difference)
            return 0  # Placeholder - needs business logic

        elif 'remark' in column_name.lower():
            # Generate remark based on drop/hike/same logic
            remarks = []
            for idx in df.index:
                remark_parts = []
                drop_val = df.at[idx, 'drop'] if 'drop' in df.columns else 0
                hike_val = df.at[idx, 'HIKE'] if 'HIKE' in df.columns else 0

                if drop_val > 0:
                    remark_parts.append('drop')
                if hike_val > 0:
                    remark_parts.append('hike')
                if not remark_parts:
                    remark_parts.append('same')

                remarks.append(', '.join(remark_parts))
            return remarks

        elif column_name in ['pct scheme -2', 'pct scheme -3', 'pct scheme -4', 'PCT Scheme-2', 'PCT Scheme-3', 'PCT Scheme-4']:
            # Additional percentage schemes (currently only 2 are implemented)
            return 0

        elif column_name in ['amount pct scheme -2', 'amount pct scheme -3', 'amount pct scheme -4', 'Amount PCT Scheme-2', 'Amount PCT Scheme-3', 'Amount PCT Scheme-4']:
            # Corresponding calculated amounts
            return 0

        else:
            # Default to 0 for numeric columns, empty string for others
            if any(keyword in column_name.lower() for keyword in ['price', 'amount', 'incentive', 'payout', 'schme', 'nlc']):
                return 0
            else:
                return ''
    
    def generate_distributor_pivot_report(self) -> pd.DataFrame:
        """Generate Distributor-wise pivot report with scheme details."""
        if self.processed_data is None:
            raise ValueError("Must run calculations first")

        logger.info("Generating distributor pivot report...")

        # Define scheme mappings (base schemes)
        scheme_mappings = [
            ('PCT Scheme-1', 'Amount PCT Scheme-1'),
            ('PCT Scheme-2', 'Amount PCT Scheme-2'),
            ('PCT Scheme-3', 'Amount PCT Scheme-3'),
            ('PCT Scheme-4', 'Amount PCT Scheme-4'),
        ]
        
        # Dynamically add PCT Scheme-5 and 6 if they exist in processed data
        if 'Amount PCT Scheme-5' in self.processed_data.columns:
            scheme_mappings.append(('PCT Scheme-5', 'Amount PCT Scheme-5'))
        if 'Amount PCT Scheme-6' in self.processed_data.columns:
            scheme_mappings.append(('PCT Scheme-6', 'Amount PCT Scheme-6'))
        
        # Add Flat Payout
        scheme_mappings.append(('Flat Payout', 'Flat Payout'))

        pivot_rows = []

        # Group by distributor (case-insensitive column lookup)
        distributor_col = None
        for col in self.processed_data.columns:
            if col.lower() in ['distributor', 'distibutor']:
                distributor_col = col
                break
        
        if distributor_col is None:
            logger.error("Distributor column not found in processed data")
            return pd.DataFrame()

        # Group by distributor
        for distributor in self.processed_data[distributor_col].unique():
            if pd.isna(distributor):
                continue

            dist_data = self.processed_data[self.processed_data[distributor_col] == distributor]

            # Check each scheme type
            for scheme_name, amount_col in scheme_mappings:
                # Sum the amount for this scheme
                total_amount = dist_data[amount_col].sum()

                # Include all schemes, even if amount is 0
                pivot_rows.append({
                    'Distributor Name': distributor,
                    'Scheme Name': scheme_name,
                    'Final AMT': int(round(total_amount, 0))
                })

        # Create DataFrame
        pivot = pd.DataFrame(pivot_rows)

        # Sort by Distributor Name, then Scheme Name
        if not pivot.empty:
            pivot = pivot.sort_values(['Distributor Name', 'Scheme Name']).reset_index(drop=True)

        logger.info(f"Generated distributor pivot with {len(pivot)} rows")
        return pivot
    
    def _fuzzy_match_model(self, target: str, candidates: List[str], threshold: int = 80) -> Optional[Tuple[str, int]]:
        """Perform fuzzy matching for model names."""
        if not candidates:
            return None
        
        result = extractOne(target, candidates, scorer=fuzz.ratio)
        if result and result[1] >= threshold:
            return result
        return None
    
    def validate_data_integrity(self) -> Tuple[List[str], Dict[str, List[str]]]:
        """Perform data integrity validations using final column names.
        
        Returns:
            Tuple of (validation_errors list, error_details dict with IMEIs)
        """
        validation_errors = []
        error_details = {}

        if self.processed_data is None:
            return ["No processed data available for validation"], {}

        # Duplicate IMEI check
        duplicates = self.processed_data[self.processed_data.duplicated('IMEI', keep=False)]
        if not duplicates.empty:
            imei_list = duplicates['IMEI'].tolist()
            validation_errors.append(f"Found {len(duplicates)} duplicate IMEIs")
            error_details['Duplicate IMEIs'] = imei_list

        # Date validation: sell out date should not be earlier than purchase date
        if 'Purchase Date' in self.processed_data.columns:
            sell_dates = pd.to_datetime(self.processed_data['Sell Out Date'], errors='coerce')
            purchase_dates = pd.to_datetime(self.processed_data['Purchase Date'], errors='coerce')

            invalid_dates_df = self.processed_data[
                (purchase_dates.notna()) &
                (sell_dates.notna()) &
                (sell_dates < purchase_dates)
            ]
            if not invalid_dates_df.empty:
                imei_list = invalid_dates_df['IMEI'].tolist()
                validation_errors.append(f"Found {len(invalid_dates_df)} records where Sell Out Date is before Purchase Date")
                error_details['Invalid Dates (Sell Out before Purchase)'] = imei_list

        missing_models_df = self.processed_data[self.processed_data['Master Model'].isna()]
        if not missing_models_df.empty:
            imei_list = missing_models_df['IMEI'].tolist()
            validation_errors.append(f"Found {len(missing_models_df)} records with missing Master Model")
            error_details['Missing Master Model'] = imei_list

        missing_prices_df = self.processed_data[self.processed_data['MOP at the Time of Purchase'].isna()]
        if not missing_prices_df.empty:
            imei_list = missing_prices_df['IMEI'].tolist()
            validation_errors.append(f"Found {len(missing_prices_df)} records with missing price data")
            error_details['Missing Price Data'] = imei_list

        return validation_errors, error_details