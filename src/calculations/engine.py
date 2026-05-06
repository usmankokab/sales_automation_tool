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

        # Ensure required columns exist, create them if missing
        if 'Total_Pct_Incentive' not in df.columns:
            logger.warning("Total_Pct_Incentive column missing, creating with default values")
            df['Total_Pct_Incentive'] = 0

        if 'Total_Flat_Incentive' not in df.columns:
            logger.warning("Total_Flat_Incentive column missing, creating with default values")
            df['Total_Flat_Incentive'] = 0

        df['Total_Incentive_Received'] = df['Total_Pct_Incentive'] + df['Total_Flat_Incentive']
        logger.info(f"Total incentives calculated: ₹{df['Total_Incentive_Received'].sum():,.0f}")

        return df

    def _step_10_nlc(self, df: pd.DataFrame) -> pd.DataFrame:
        """Step 10: Calculate Net Landing Cost (NLC)."""
        logger.info("Step 10: Calculating Net Landing Cost...")

        # Ensure required columns exist
        if 'Matched_Price' not in df.columns:
            logger.warning("Matched_Price column missing, using Purchase_Price as fallback")
            df['Matched_Price'] = df.get('Purchase_Price', 0)

        if 'Drop_Amount' not in df.columns:
            logger.warning("Drop_Amount column missing, assuming 0")
            df['Drop_Amount'] = 0

        if 'Total_Incentive_Received' not in df.columns:
            logger.warning("Total_Incentive_Received column missing, assuming 0")
            df['Total_Incentive_Received'] = 0

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

        logger.info(f"NLC calculations completed. Total NLC: ₹{df['Calculated_NLC'].sum():,.0f}")
        return df

    def _step_11_final_validation(self, df: pd.DataFrame) -> pd.DataFrame:
        """Step 11: Final validation and cleanup with exact column ordering."""
        logger.info("Step 11: Performing final validation and column ordering...")

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

        # Create the exact column order as specified in the sales sheet
        final_columns = [
            'IMEI',
            'sell out date',
            'activation date',
            'master modal',
            'SERIES',  # To be derived from master modal
            'distibutor',
            'purchase date',
            'purchase price',
            'MOP AT THE TIME OF PURCHASE',  # Matched purchase price from price list
            'current mop/srp',
            'bill less in invoice ',
            'invoice price (pre gst amount',
            'drop',
            'hike (now compare the master model in price list to chq the current price falls in date validation -1 or date validation -2 for that you take the sell out date of master model) and in case not active then by default date validation -1',
            'HIKE',
            'remark (drop,hike,same (drop and hike both)',
            'final price (g-k)',
            'pre gst price (final price',
            'pct scheme -1',
            'amount pct sceme -1',
            'pct scheme -2',
            'amount pct sceme -2',
            'pct scheme -3',
            'amount pct sceme -3',
            'pct scheme -4',
            'amount pct sceme -4',
            'flat payout-1',
            'flat payout-2',
            'flat payout-3',
            'flat payout-4',
            'total schme rcvd',
            'nt nlc (o-ac)',
            # Additional columns needed for charts (not in original spec but needed for functionality)
            'Total_Pct_Incentive',
            'Total_Flat_Incentive'
        ]

        # Map existing columns to the required names (preserve original sales sheet structure)
        column_mapping = {
            'IMEI': 'IMEI',
            'sell out date': 'sell out date',
            'activation date': 'activation date',
            'master modal': 'master modal',
            # SERIES - will be derived
            'distibutor': 'distibutor',  # Fix typo
            'purchase date': 'purchase date',
            'purchase price': 'purchase price',
            # MOP AT THE TIME OF PURCHASE - will be matched price
            'current mop/srp': 'current mop/srp',
            'bill less in invoice ': 'bill less in invoice ',
            'invoice price (pre gst amount': 'invoice price (pre gst amount',
            'drop': 'drop',
            'hike (now compare the master model in price list to chq the current price falls in date validation -1 or date validation -2 for that you take the sell out date of master model) and in case not active then by default date validation -1': 'hike (now compare the master model in price list to chq the current price falls in date validation -1 or date validation -2 for that you take the sell out date of master model) and in case not active then by default date validation -1',
            'HIKE': 'HIKE',
            'remark (drop,hike,same (drop and hike both)': 'remark (drop,hike,same (drop and hike both)',
            'final price (g-k)': 'final price (g-k)',
            'pre gst price (final price': 'pre gst price (final price',
            'pct scheme -1': 'pct scheme -1',
            'amount pct sceme -1': 'amount pct sceme -1',
            'pct scheme -2': 'pct scheme -2',
            'amount pct sceme -2': 'amount pct sceme -2',
            'pct scheme -3': 'pct scheme -3',
            'amount pct sceme -3': 'amount pct sceme -3',
            'pct scheme -4': 'pct scheme -4',
            'amount pct sceme -4': 'amount pct sceme -4',
            'flat payout-1': 'flat payout-1',
            'flat payout-2': 'flat payout-2',
            'flat payout-3': 'flat payout-3',
            'flat payout-4': 'flat payout-4',
            'total schme rcvd': 'total schme rcvd',
            'nt nlc (o-ac)': 'nt nlc (o-ac)',
            'Total_Pct_Incentive': 'Total_Pct_Incentive',
            'Total_Flat_Incentive': 'Total_Flat_Incentive'
        }

        # Start with original sales data structure and update with calculations
        final_df = df.copy()

        # Ensure all required columns exist with proper names
        for required_col in final_columns:
            if required_col not in final_df.columns:
                if required_col in column_mapping and column_mapping[required_col] in final_df.columns:
                    # Column exists with different name, rename it
                    final_df[required_col] = final_df[column_mapping[required_col]]
                else:
                    # Column doesn't exist, add it
                    final_df[required_col] = self._get_default_value_for_column(required_col, final_df)

        # Update calculated columns with the correct values
        if 'Matched_Price' in final_df.columns:
            final_df['MOP AT THE TIME OF PURCHASE'] = final_df['Matched_Price']

        if 'Calculated_Final_Price' in final_df.columns:
            final_df['final price (g-k)'] = final_df['Calculated_Final_Price']

        if 'Calculated_NLC' in final_df.columns:
            final_df['nt nlc (o-ac)'] = final_df['Calculated_NLC']

        if 'Total_Incentive_Received' in final_df.columns:
            final_df['total schme rcvd'] = final_df['Total_Incentive_Received']

        # Handle percentage scheme columns
        if 'Pct_Incentive_1' in final_df.columns:
            final_df['pct scheme -1'] = final_df['Pct_Incentive_1']
            final_df['amount pct sceme -1'] = final_df['Pct_Incentive_1']  # This should be the calculated amount

        if 'Pct_Incentive_2' in final_df.columns:
            final_df['pct scheme -2'] = final_df['Pct_Incentive_2']
            final_df['amount pct sceme -2'] = final_df['Pct_Incentive_2']

        # Handle flat payout columns
        if 'Flat_Incentive' in final_df.columns:
            final_df['flat payout-1'] = final_df['Flat_Incentive']

        # Preserve intermediate columns needed for charts
        if 'Total_Pct_Incentive' in final_df.columns:
            final_df['Total_Pct_Incentive'] = final_df['Total_Pct_Incentive']

        if 'Total_Flat_Incentive' in final_df.columns:
            final_df['Total_Flat_Incentive'] = final_df['Total_Flat_Incentive']

        # Add processing status (but don't include it in final output)
        processing_status = pd.Series('Completed', index=final_df.index)
        processing_status.loc[final_df['sell out date'].isna()] = 'Date_Missing'
        processing_status.loc[final_df['master modal'].isna()] = 'Model_Missing'

        # Reorder columns to match exact specification (exclude processing status)
        final_df = final_df[final_columns]

        # Log processing status for debugging (don't add to final output)
        logger.info(f"Processing status: {processing_status.value_counts().to_dict()}")

        logger.info(f"Final column ordering completed. Shape: {final_df.shape}")
        return final_df

    def _get_default_value_for_column(self, column_name: str, df: pd.DataFrame):
        """Get default value for columns that don't exist in current data."""
        if column_name == 'SERIES':
            # Try to extract series from master modal (e.g., "REALME" from "REALME C71 4@64")
            if 'master modal' in df.columns:
                return df['master modal'].str.split().str[0]
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

        elif column_name in ['pct scheme -2', 'pct scheme -3', 'pct scheme -4']:
            # Additional percentage schemes (currently only 2 are implemented)
            return 0

        elif column_name in ['amount pct sceme -2', 'amount pct sceme -3', 'amount pct sceme -4']:
            # Corresponding calculated amounts
            return 0

        elif column_name in ['flat payout-2', 'flat payout-3', 'flat payout-4']:
            # Additional flat payouts (currently only 1 is implemented)
            return 0

        else:
            # Default to 0 for numeric columns, empty string for others
            if any(keyword in column_name.lower() for keyword in ['price', 'amount', 'incentive', 'payout', 'schme', 'nlc']):
                return 0
            else:
                return ''
    
    def generate_pivot_report(self) -> pd.DataFrame:
        """Generate Distributor-wise pivot report from processed data."""
        if self.processed_data is None:
            raise ValueError("Must run calculations first")

        logger.info("Generating pivot report...")

        # Use the final column names from processed data
        pivot = pd.pivot_table(
            self.processed_data,
            values=['total schme rcvd', 'nt nlc (o-ac)', 'final price (g-k)'],
            index='distibutor',
            aggfunc='sum'
        ).reset_index()

        # Rename columns for clarity
        pivot.columns = ['Distributor', 'Total_Incentives', 'Total_NLC', 'Total_Final_Price']
        pivot['Total_Margin'] = pivot['Total_Final_Price'] - pivot['Total_NLC']

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
        """Perform data integrity validations using final column names."""
        validation_errors = []

        if self.processed_data is None:
            return ["No processed data available for validation"]

        # Duplicate IMEI check
        duplicates = self.processed_data[self.processed_data.duplicated('IMEI', keep=False)]
        if not duplicates.empty:
            validation_errors.append(f"Found {len(duplicates)} duplicate IMEIs")

        # Date validation: sell out date should not be earlier than purchase date
        if 'purchase date' in self.processed_data.columns:
            sell_dates = pd.to_datetime(self.processed_data['sell out date'], errors='coerce')
            purchase_dates = pd.to_datetime(self.processed_data['purchase date'], errors='coerce')

            invalid_dates = self.processed_data[
                (purchase_dates.notna()) &
                (sell_dates.notna()) &
                (sell_dates < purchase_dates)
            ]
            if not invalid_dates.empty:
                validation_errors.append(f"Found {len(invalid_dates)} records where Sell Out Date is before Purchase Date")

        # Missing critical data
        missing_models = self.processed_data['master modal'].isna().sum()
        if missing_models > 0:
            validation_errors.append(f"Found {missing_models} records with missing Master Model")

        # Check for missing price data
        missing_prices = self.processed_data['MOP AT THE TIME OF PURCHASE'].isna().sum()
        if missing_prices > 0:
            validation_errors.append(f"Found {missing_prices} records with missing price data")

        return validation_errors