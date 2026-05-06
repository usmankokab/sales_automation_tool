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
                 scheme_file: pd.DataFrame, sales_data: pd.DataFrame):
        """
        Initialize with all required data sources from workbook.

        Args:
            drop_dump: DataFrame containing drop IMEIs and amounts
            price_list: DataFrame with pricing information
            scheme_file: DataFrame with scheme definitions
            sales_data: DataFrame with sales transactions
        """
        self.drop_dump = drop_dump.copy()
        self.price_list = price_list.copy()
        self.scheme_file = scheme_file.copy()
        self.sales_data = sales_data.copy()
        self.processed_data = None
        self.errors = []

        # Initialize fuzzy matching cache
        self._model_cache = {}

    def run_calculations(self) -> Tuple[pd.DataFrame, List[str]]:
        """
        Execute the complete 11-step calculation process.

        Returns:
            Tuple of (processed DataFrame, list of error messages)
        """
        logger.info("Starting SIAT calculation process...")

        # Pre-processing validation
        self._validate_input_data()

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
            logger.info(f"After Step 7-8: {df.shape}")

            # Step 9: Incentive Sum
            logger.info("Executing Step 9: Incentive Sum")
            df = self._step_9_incentive_sum(df)
            logger.info(f"After Step 9: {df.shape}")

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

        # Check price list
        if self.price_list.empty:
            raise ValueError("Price list is empty")

        required_price_cols = ['Master_Model', 'Purchase_Price']
        missing_cols = [col for col in required_price_cols if col not in self.price_list.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns in price list: {missing_cols}")

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

        # Always add/update the 'drop' column for Column K
        df['drop'] = df['Drop_Amount']

        drop_count = df['Has_Drop'].sum()
        total_drop_value = df['Drop_Amount'].sum()

        logger.info(f"Found {drop_count} drops with total value ₹{total_drop_value:,.0f} out of {len(df)} records")
        return df
    
    def _step_3_4_price_match(self, df: pd.DataFrame) -> pd.DataFrame:
        """Step 3-4: Lookup Master Model in Price List with date validation."""
        logger.info("Step 3-4: Performing price matching and validation...")

        # Ensure date columns are datetime
        df['Sell_Out_Date'] = pd.to_datetime(df['Sell_Out_Date'], errors='coerce')
        self.price_list['Valid_From'] = pd.to_datetime(self.price_list['Valid_From'], errors='coerce')
        self.price_list['Valid_To'] = pd.to_datetime(self.price_list['Valid_To'], errors='coerce')

        # Create lookup function with caching for better performance
        def get_price_info(row):
            master_model = row.get('Master_Model', '')
            sell_date = row['Sell_Out_Date']

            if pd.isna(master_model) or pd.isna(sell_date) or not master_model:
                return pd.Series({'Matched_Price': np.nan, 'Pre_GST_Price': np.nan})

            # Use cached fuzzy match
            if master_model not in self._model_cache:
                best_match = self._fuzzy_match_model(
                    str(master_model),
                    self.price_list['Master_Model'].dropna().astype(str).tolist()
                )
                self._model_cache[master_model] = best_match

            best_match = self._model_cache[master_model]

            if best_match:
                # Find price within date range
                mask = (
                    (self.price_list['Master_Model'].astype(str) == best_match[0]) &
                    (self.price_list['Valid_From'] <= sell_date) &
                    (self.price_list['Valid_To'] >= sell_date)
                )
                matching_prices = self.price_list[mask]

                if not matching_prices.empty:
                    purchase_price = matching_prices['Purchase_Price'].iloc[0]
                    pre_gst_price = matching_prices.get('Pre_GST_Price', purchase_price).iloc[0]
                    return pd.Series({
                        'Matched_Price': purchase_price,
                        'Pre_GST_Price': pre_gst_price
                    })
                else:
                    self.errors.append(f"No valid price found for model {best_match[0]} on date {sell_date}")
                    return pd.Series({'Matched_Price': np.nan, 'Pre_GST_Price': np.nan})
            else:
                self.errors.append(f"No matching model found for {master_model}")
                return pd.Series({'Matched_Price': np.nan, 'Pre_GST_Price': np.nan})

        # Apply price matching
        price_info = df.apply(get_price_info, axis=1)
        df['Matched_Price'] = price_info['Matched_Price']
        df['Price_List_Pre_GST'] = price_info['Pre_GST_Price']

        matched_count = df['Matched_Price'].notna().sum()
        logger.info(f"Successfully matched prices for {matched_count} out of {len(df)} records")
        return df
    
    def _step_5_6_tax_base(self, df: pd.DataFrame) -> pd.DataFrame:
        """Step 5-6: Calculate Final Price and Pre-GST Price."""
        logger.info("Step 5-6: Calculating tax base...")

        # Use Matched_Price if available, otherwise use Purchase_Price
        base_price_col = 'Matched_Price' if 'Matched_Price' in df.columns else 'Purchase_Price'

        # Final Price = Base Price - Drop Amount
        df['Tax_Base_Final_Price'] = df[base_price_col] - df['Drop_Amount']

        # Pre-GST Price = Final Price / 1.18
        df['Tax_Base_Pre_GST_Price'] = df['Tax_Base_Final_Price'] / 1.18

        # For compatibility, also set standard names
        df['Final_Price'] = df['Tax_Base_Final_Price']
        df['Pre_GST_Price'] = df['Tax_Base_Pre_GST_Price']

        return df
    
    def _step_7_8_scheme_application(self, df: pd.DataFrame) -> pd.DataFrame:
        """Step 7-8: Apply schemes based on Master Model and Sell Out Date."""
        logger.info("Step 7-8: Applying schemes...")

        # Ensure scheme dates are datetime
        self.scheme_file['Scheme_Start_Date'] = pd.to_datetime(self.scheme_file['Scheme_Start_Date'], errors='coerce')
        self.scheme_file['Scheme_End_Date'] = pd.to_datetime(self.scheme_file['Scheme_End_Date'], errors='coerce')

        def apply_scheme(row):
            master_model = row.get('Master_Model', '')
            sell_date = row['Sell_Out_Date']
            pre_gst_price = row.get('Price_List_Pre_GST', row.get('Pre_GST_Price', 0))

            if pd.isna(master_model) or pd.isna(sell_date) or pd.isna(pre_gst_price) or pre_gst_price == 0:
                return pd.Series({
                    'Pct_Incentive_1': 0, 'Pct_Incentive_2': 0, 'Flat_Incentive': 0,
                    'Total_Pct_Incentive': 0, 'Total_Flat_Incentive': 0
                })

            # Use cached fuzzy match
            if master_model not in self._model_cache:
                best_match = self._fuzzy_match_model(
                    str(master_model),
                    self.scheme_file['Master_Model'].dropna().astype(str).tolist()
                )
                self._model_cache[master_model] = best_match

            best_match = self._model_cache[master_model]

            if best_match:
                # Find applicable schemes within date range
                mask = (
                    (self.scheme_file['Master_Model'].astype(str) == best_match[0]) &
                    (self.scheme_file['Scheme_Start_Date'] <= sell_date) &
                    (self.scheme_file['Scheme_End_Date'] >= sell_date)
                )
                applicable_schemes = self.scheme_file[mask]

                pct_incentive_1 = 0
                pct_incentive_2 = 0
                flat_incentive = 0

                for _, scheme in applicable_schemes.iterrows():
                    # Apply percentage schemes
                    pct_1 = scheme.get('Pct_Scheme_1', 0)
                    if pd.notna(pct_1) and pct_1 > 0:
                        pct_incentive_1 += pre_gst_price * (pct_1 / 100)

                    pct_2 = scheme.get('Pct_Scheme_2', 0)
                    if pd.notna(pct_2) and pct_2 > 0:
                        pct_incentive_2 += pre_gst_price * (pct_2 / 100)

                    # Apply flat schemes
                    flat = scheme.get('Flat_Scheme', 0)
                    if pd.notna(flat) and flat > 0:
                        flat_incentive += flat

                total_pct = pct_incentive_1 + pct_incentive_2
                total_flat = flat_incentive

                return pd.Series({
                    'Pct_Incentive_1': pct_incentive_1,
                    'Pct_Incentive_2': pct_incentive_2,
                    'Flat_Incentive': flat_incentive,
                    'Total_Pct_Incentive': total_pct,
                    'Total_Flat_Incentive': total_flat
                })
            else:
                return pd.Series({
                    'Pct_Incentive_1': 0, 'Pct_Incentive_2': 0, 'Flat_Incentive': 0,
                    'Total_Pct_Incentive': 0, 'Total_Flat_Incentive': 0
                })

        # Apply scheme calculations
        scheme_results = df.apply(apply_scheme, axis=1)
        df = pd.concat([df, scheme_results], axis=1)

        total_schemes = (df['Total_Pct_Incentive'] + df['Total_Flat_Incentive']).sum()
        logger.info(f"Applied schemes with total incentive value ₹{total_schemes:,.0f}")
        return df
    
    def _step_9_incentive_sum(self, df: pd.DataFrame) -> pd.DataFrame:
        """Step 9: Aggregate all incentives into Total Incentive Received."""
        logger.info("Step 9: Calculating total incentives...")

        df['Total_Incentive_Received'] = df['Total_Pct_Incentive'] + df['Total_Flat_Incentive']

        return df

    def _step_10_nlc(self, df: pd.DataFrame) -> pd.DataFrame:
        """Step 10: Calculate Net Landing Cost (NLC)."""
        logger.info("Step 10: Calculating Net Landing Cost...")

        # Final Price = Matched Price - Drop Amount
        df['Calculated_Final_Price'] = df['Matched_Price'] - df['Drop_Amount']

        # NLC = Final Price - Total Incentive Received
        df['Calculated_NLC'] = df['Calculated_Final_Price'] - df['Total_Incentive_Received']

        # Calculate margin
        df['Calculated_Margin'] = df['Matched_Price'] - df['Calculated_NLC']

        # For backward compatibility, also set the standard column names
        df['Final_Price'] = df['Calculated_Final_Price']
        df['NLC'] = df['Calculated_NLC']
        df['Margin'] = df['Calculated_Margin']

        return df

    def _step_11_final_validation(self, df: pd.DataFrame) -> pd.DataFrame:
        """Step 11: Final validation and cleanup."""
        logger.info("Step 11: Performing final validation...")

        # Validate date consistency
        if 'Purchase_Date' in df.columns:
            df['Purchase_Date'] = pd.to_datetime(df['Purchase_Date'], errors='coerce')
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

        # Add summary statistics
        df['Processing_Status'] = 'Completed'
        df.loc[df['Matched_Price'].isna(), 'Processing_Status'] = 'Price_Missing'
        df.loc[df['Master_Model'].isna(), 'Processing_Status'] = 'Model_Missing'

        logger.info("Final validation completed")
        return df
    
    def generate_pivot_report(self) -> pd.DataFrame:
        """Step 11: Generate Distributor-wise pivot report."""
        if self.processed_data is None:
            raise ValueError("Must run calculations first")
        
        logger.info("Step 11: Generating pivot report...")
        
        pivot = pd.pivot_table(
            self.processed_data,
            values=['Total_Incentive_Received', 'NLC', 'Final_Price'],
            index='Distributor',
            aggfunc='sum'
        ).reset_index()
        
        return pivot
    
    def _fuzzy_match_model(self, target: str, candidates: List[str], threshold: int = 80) -> Optional[Tuple[str, int]]:
        """Perform fuzzy matching for model names."""
        if not candidates:
            return None
        
        result = extractOne(target, candidates, scorer=fuzz.ratio)
        if result and result[1] >= threshold:
            return result
        return None
    
    def validate_data_integrity(self) -> List[str]:
        """Perform data integrity validations."""
        validation_errors = []
        
        if self.processed_data is None:
            return ["No processed data available for validation"]
        
        # Duplicate IMEI check
        duplicates = self.processed_data[self.processed_data.duplicated('IMEI', keep=False)]
        if not duplicates.empty:
            validation_errors.append(f"Found {len(duplicates)} duplicate IMEIs")
        
        # Date validation: Sell Out Date should not be earlier than Purchase Date
        if 'Purchase_Date' in self.processed_data.columns:
            invalid_dates = self.processed_data[
                pd.to_datetime(self.processed_data['Sell_Out_Date']) < 
                pd.to_datetime(self.processed_data['Purchase_Date'])
            ]
            if not invalid_dates.empty:
                validation_errors.append(f"Found {len(invalid_dates)} records where Sell Out Date is before Purchase Date")
        
        # Missing critical data
        missing_models = self.processed_data['Master_Model'].isna().sum()
        if missing_models > 0:
            validation_errors.append(f"Found {missing_models} records with missing Master Model")
        
        return validation_errors