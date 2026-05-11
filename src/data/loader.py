import pandas as pd
import numpy as np
from typing import Union, Optional, Dict, Any, Tuple
import logging
import os
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from datetime import datetime

logger = logging.getLogger(__name__)

class DataLoader:
    """Handles loading of data from a single Excel workbook with multiple sheets."""

    @staticmethod
    def load_workbook(file_path: str) -> Dict[str, pd.DataFrame]:
        """
        Load all sheets from the Excel workbook.

        Args:
            file_path: Path to the Excel workbook

        Returns:
            Dictionary with sheet names as keys and DataFrames as values
        """
        try:
            xl = pd.ExcelFile(file_path)
            sheets_data = {}

            for sheet_name in xl.sheet_names:
                try:
                    # Load each sheet with appropriate header handling
                    if sheet_name.lower() == 'drop dump':
                        # Drop dump has headers on row 0
                        df = pd.read_excel(xl, sheet_name=sheet_name, header=0)
                    elif sheet_name.lower() == 'scheme':
                        # Scheme sheet: try to detect header row automatically
                        # Read first few rows to find where actual data starts
                        temp_df = pd.read_excel(xl, sheet_name=sheet_name, header=None, nrows=10)
                        
                        # Find the row that contains 'Master Model' or 'master model'
                        header_row = 0
                        for idx, row in temp_df.iterrows():
                            row_str = ' '.join([str(val).lower() for val in row if pd.notna(val)])
                            if 'master model' in row_str or 'master' in row_str:
                                header_row = idx
                                break
                        
                        # Now load with correct header row
                        df = pd.read_excel(xl, sheet_name=sheet_name, header=header_row)
                        logger.info(f"Scheme sheet loaded with header at row {header_row}")
                    elif sheet_name.lower() in ['sales', 'price list']:
                        # These sheets have headers on row 0
                        df = pd.read_excel(xl, sheet_name=sheet_name, header=0)
                    else:
                        # Other sheets (like pivot) may not have structured data
                        df = pd.read_excel(xl, sheet_name=sheet_name, header=None)

                    sheets_data[sheet_name.lower()] = df
                    logger.info(f"Loaded sheet '{sheet_name}' with shape {df.shape}")

                except Exception as e:
                    logger.warning(f"Error loading sheet '{sheet_name}': {str(e)}")
                    sheets_data[sheet_name.lower()] = pd.DataFrame()

            return sheets_data

        except Exception as e:
            logger.error(f"Error loading workbook {file_path}: {str(e)}")
            raise

    @staticmethod
    def extract_data_sources(workbook_data: Dict[str, pd.DataFrame]) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Extract the four required data sources from the workbook.

        Args:
            workbook_data: Dictionary of all sheets from the workbook

        Returns:
            Tuple of (sales_data, price_list, scheme_file, drop_dump)
        """
        logger.info(f"Available sheets in workbook: {list(workbook_data.keys())}")

        # Extract sales data - try multiple possible sheet names
        sales_data = None
        for sheet_name in ['sales', 'Sales', 'SALES']:
            if sheet_name in workbook_data and not workbook_data[sheet_name].empty:
                sales_data = workbook_data[sheet_name]
                logger.info(f"Found sales data in sheet: {sheet_name}")
                break

        if sales_data is None or sales_data.empty:
            raise ValueError("Sales sheet ('sales') not found or empty in workbook")

        # Extract price list - try multiple possible sheet names
        price_list = None
        for sheet_name in ['price list', 'price_list', 'Price List', 'pricelist']:
            if sheet_name in workbook_data and not workbook_data[sheet_name].empty:
                price_list = workbook_data[sheet_name]
                logger.info(f"Found price list in sheet: {sheet_name}")
                break

        if price_list is None or price_list.empty:
            raise ValueError("Price List sheet ('price list') not found or empty in workbook")

        # Extract scheme file - try multiple possible sheet names
        scheme_file = None
        for sheet_name in ['scheme', 'Scheme', 'SCHEME']:
            if sheet_name in workbook_data and not workbook_data[sheet_name].empty:
                scheme_file = workbook_data[sheet_name]
                logger.info(f"Found scheme data in sheet: {sheet_name}")
                break

        if scheme_file is None or scheme_file.empty:
            raise ValueError("Scheme sheet ('scheme') not found or empty in workbook")

        # Extract drop dump - try multiple possible sheet names
        drop_dump = None
        for sheet_name in ['drop dump', 'drop_dump', 'Drop Dump', 'dropdump']:
            if sheet_name in workbook_data and not workbook_data[sheet_name].empty:
                drop_dump = workbook_data[sheet_name]
                logger.info(f"Found drop dump in sheet: {sheet_name}")
                break

        if drop_dump is None or drop_dump.empty:
            raise ValueError("Drop Dump sheet ('drop dump') not found or empty in workbook")

        logger.info(f"Data shapes - Sales: {sales_data.shape}, Price: {price_list.shape}, Scheme: {scheme_file.shape}, Drop: {drop_dump.shape}")

        # Standardize column names
        sales_data = DataLoader._standardize_sales_columns(sales_data)
        price_list = DataLoader._standardize_price_columns(price_list)
        scheme_file = DataLoader._standardize_scheme_columns(scheme_file)
        drop_dump = DataLoader._standardize_drop_columns(drop_dump)

        return sales_data, price_list, scheme_file, drop_dump

    @staticmethod
    def _standardize_sales_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names for sales data."""
        # Convert all column names to lowercase first for consistent mapping
        df.columns = df.columns.str.lower().str.strip()

        column_mapping = {
            'imei': 'IMEI',
            'sell out date': 'Sell_Out_Date',
            'master modal': 'Master_Model',
            'master_modal': 'Master_Model',
            'master model': 'Master_Model',
            'distibutor': 'Distributor',
            'distributor': 'Distributor',
            'purchase date': 'Purchase_Date',
            'purchase price': 'Purchase_Price',
            'bill less in invoice': 'Bill_Less_Invoice',
            'bill less in invoice ': 'Bill_Less_Invoice',
            'series': 'SERIES',
            'drop': 'Original_Drop',  # Rename existing drop column to avoid conflicts
        }

        df = df.rename(columns=column_mapping)

        # Ensure required columns exist
        required_cols = ['IMEI', 'Sell_Out_Date', 'Master_Model', 'Distributor']
        missing_cols = []
        for col in required_cols:
            if col not in df.columns:
                missing_cols.append(col)

        if missing_cols:
            logger.warning(f"Required columns not found in sales data: {missing_cols}")
            # Try to find similar columns
            for missing in missing_cols:
                similar_cols = [c for c in df.columns if missing.lower() in c.lower()]
                if similar_cols:
                    logger.info(f"Using '{similar_cols[0]}' for '{missing}'")

        return df

    @staticmethod
    def _standardize_price_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names for price list."""
        column_mapping = {
            'Master Model': 'Master_Model',
            'master model': 'Master_Model',
            'valid from': 'Valid_From',
            'valid_from': 'Valid_From',
            'valid to': 'Valid_To',
            'valid_to': 'Valid_To',
            'Net Purchase 4%': 'Purchase_Price',
            'purchase_price': 'Purchase_Price',
            'pre gst price': 'Pre_GST_Price',
            'pre_gst_price': 'Pre_GST_Price',
        }

        df = df.rename(columns=column_mapping)
        return df

    @staticmethod
    def _standardize_scheme_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names for scheme file."""
        # Lowercase all columns first for consistent matching
        df.columns = df.columns.str.lower().str.strip()
        
        logger.info(f"Scheme columns after lowercase: {list(df.columns)}")

        column_mapping = {
            'master model': 'Master_Model',
            'master_model': 'Master_Model',
            'master': 'Master_Model',
            'model': 'Master_Model',
            'start date': 'Scheme_Start_Date',
            'start_date': 'Scheme_Start_Date',
            'scheme start date': 'Scheme_Start_Date',
            'scheme_start_date': 'Scheme_Start_Date',
            'start': 'Scheme_Start_Date',
            'from date': 'Scheme_Start_Date',
            'end date': 'Scheme_End_Date',
            'end_date': 'Scheme_End_Date',
            'scheme end date': 'Scheme_End_Date',
            'scheme_end_date': 'Scheme_End_Date',
            'end': 'Scheme_End_Date',
            'to date': 'Scheme_End_Date',
            'pct scheme -1': 'Pct_Scheme_1',
            'pct scheme -2': 'Pct_Scheme_2',
            'pct scheme -3': 'Pct_Scheme_3',
            'pct scheme -4': 'Pct_Scheme_4',
            'flat schme': 'Flat_Scheme',
            'flat scheme': 'Flat_Scheme',
            'flat_scheme': 'Flat_Scheme',
            'flat': 'Flat_Scheme',
        }

        df = df.rename(columns=column_mapping)
        
        logger.info(f"Scheme columns after mapping: {list(df.columns)}")
        
        # If still missing required columns, try to find them by pattern matching
        if 'Master_Model' not in df.columns:
            for col in df.columns:
                if 'model' in col.lower() or 'master' in col.lower():
                    df = df.rename(columns={col: 'Master_Model'})
                    logger.info(f"Mapped '{col}' to 'Master_Model'")
                    break
        
        if 'Scheme_Start_Date' not in df.columns:
            for col in df.columns:
                if 'start' in col.lower() or 'from' in col.lower():
                    df = df.rename(columns={col: 'Scheme_Start_Date'})
                    logger.info(f"Mapped '{col}' to 'Scheme_Start_Date'")
                    break
        
        if 'Scheme_End_Date' not in df.columns:
            for col in df.columns:
                if 'end' in col.lower() or 'to' in col.lower():
                    df = df.rename(columns={col: 'Scheme_End_Date'})
                    logger.info(f"Mapped '{col}' to 'Scheme_End_Date'")
                    break

        # Convert percentage columns from whole numbers to decimals (e.g., 2.5 -> 0.025)
        # Store original percentage values for display
        percentage_columns = ['Pct_Scheme_1', 'Pct_Scheme_2', 'Pct_Scheme_3', 'Pct_Scheme_4']
        for col in percentage_columns:
            if col in df.columns:
                logger.info(f"Scheme column {col} sample value: {df[col].iloc[0] if len(df) > 0 else 'empty'}")
                # Keep original percentage values, don't convert to decimal
                # The calculation will handle the conversion

        return df

    @staticmethod
    def _standardize_drop_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names for drop dump."""
        # Convert all column names to lowercase for consistent mapping
        df.columns = df.columns.str.lower().str.strip()

        column_mapping = {
            'imei': 'IMEI',
            'drop amount': 'Drop_Amount',
            'drop_amount': 'Drop_Amount',
        }

        df = df.rename(columns=column_mapping)

        logger.info(f"Drop dump columns after standardization: {list(df.columns)}")

        # Validate required columns exist
        if 'IMEI' not in df.columns:
            raise ValueError("Drop dump sheet must contain 'IMEI' or 'imei' column")

        if 'Drop_Amount' not in df.columns:
            logger.warning("Drop dump sheet missing 'Drop_Amount' column, assuming 0 for all records")
            df['Drop_Amount'] = 0

        return df

    @staticmethod
    def save_results_to_workbook(
        input_file: str,
        processed_data: pd.DataFrame,
        pivot_data: pd.DataFrame,
        output_file: Optional[str] = None
    ) -> str:
        """
        Save processed results as a beautifully formatted Excel file.

        Args:
            input_file: Path to the input workbook
            processed_data: Processed sales data with calculations
            pivot_data: Distributor pivot table data
            output_file: Optional output file path

        Returns:
            Path to the saved file in output folder
        """
        try:
            # Generate output filename
            if output_file is None:
                base_name = os.path.splitext(os.path.basename(input_file))[0]
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = f"{base_name}_processed_{timestamp}.xlsx"

            # Prepare dataframes for Excel export
            dataframes = {
                'Processed Sales Data': processed_data
            }

            # Add distributor pivot if available
            if pivot_data is not None and not pivot_data.empty:
                dataframes['Distributor Pivot'] = pivot_data

            # Create beautifully formatted Excel file
            filepath = DataLoader.create_beautiful_excel(dataframes, output_file)

            logger.info(f"Excel results saved to {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error saving results: {str(e)}")
            raise

    @staticmethod
    def _create_summary_sheet(processed_data: pd.DataFrame, pivot_data: pd.DataFrame) -> pd.DataFrame:
        """Create a summary sheet with key metrics."""
        summary = []

        # Overall metrics (with safe column access)
        total_incentives = processed_data.get('Total_Incentive_Received', pd.Series()).sum()
        total_nlc = processed_data.get('NLC', processed_data.get('Calculated_NLC', pd.Series())).sum()
        total_margin = processed_data.get('Margin', processed_data.get('Calculated_Margin', pd.Series())).sum()
        total_records = len(processed_data)

        summary.extend([
            ['SIAT PROCESSING SUMMARY'],
            ['Generated on:', pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')],
            [''],
            ['OVERALL METRICS'],
            ['Total Records Processed', total_records],
            ['Total Incentives Paid', f"₹{total_incentives:,.0f}"],
            ['Total Net Landing Cost', f"₹{total_nlc:,.0f}"],
            ['Total Margin Earned', f"₹{total_margin:,.0f}"],
            ['Average Incentive per Record', f"₹{total_incentives/total_records:,.0f}" if total_records > 0 else 'N/A'],
            [''],
            ['DISTRIBUTOR BREAKDOWN'],
            ['Distributor', 'Total Incentives', 'Margin %'],
        ])

        # Add distributor data
        if pivot_data is not None and not pivot_data.empty:
            for _, row in pivot_data.iterrows():
                summary.append([
                    row.get('Distributor', 'Unknown'),
                    f"₹{row.get('Total_Incentive_Received', 0):,.0f}",
                    f"{row.get('Margin_Percentage', row.get('Margin', 0)):.1f}%"
                ])
        else:
            summary.append(['No distributor data available', '', ''])

        return pd.DataFrame(summary)

    @staticmethod
    def create_beautiful_excel(dataframes: Dict[str, pd.DataFrame], filename: str = None) -> str:
        """
        Create a professionally formatted Excel file with multiple sheets.

        Args:
            dataframes: Dictionary of sheet names to DataFrames
            filename: Output filename (auto-generated if None)

        Returns:
            Path to the created Excel file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"SIAT_Report_{timestamp}.xlsx"

        # Create output folder if it doesn't exist
        output_folder = "output"
        os.makedirs(output_folder, exist_ok=True)
        filepath = os.path.join(output_folder, filename)

        # Create workbook
        wb = Workbook()

        # Remove default sheet
        wb.remove(wb.active)

        for sheet_name, df in dataframes.items():
            ws = wb.create_sheet(title=sheet_name)

            # Write data
            DataLoader._write_formatted_sheet(ws, df, sheet_name)

        # Save workbook
        wb.save(filepath)
        logger.info(f"Beautiful Excel file created: {filepath}")

        return filepath

    @staticmethod
    def _write_formatted_sheet(ws, df: pd.DataFrame, sheet_title: str):
        """Write a DataFrame to a worksheet with professional formatting."""
        # Define styles
        header_font = Font(name='Calibri', size=12, bold=True, color='FFFFFF')
        header_fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
        header_alignment = Alignment(horizontal='center', vertical='center')

        data_font = Font(name='Calibri', size=10)
        data_alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)

        border = Border(
            left=Side(style='thin', color='000000'),
            right=Side(style='thin', color='000000'),
            top=Side(style='thin', color='000000'),
            bottom=Side(style='thin', color='000000')
        )

        # Add title row
        title_font = Font(name='Calibri', size=14, bold=True, color='366092')
        title_alignment = Alignment(horizontal='center', vertical='center')

        ws.merge_cells('A1:Z1')
        title_cell = ws['A1']
        title_cell.value = f"SIAT Report - {sheet_title}"
        title_cell.font = title_font
        title_cell.alignment = title_alignment

        # Add metadata
        ws['A2'] = f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ws['A2'].font = Font(name='Calibri', size=9, italic=True)

        # Write headers
        headers = df.columns.tolist()
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=4, column=col_num, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = border

        # Write data with formatting
        for row_num, row in enumerate(df.itertuples(index=False), 5):
            # Alternate row colors
            if row_num % 2 == 0:
                row_fill = PatternFill(start_color='F2F2F2', end_color='F2F2F2', fill_type='solid')
            else:
                row_fill = PatternFill(start_color='FFFFFF', end_color='FFFFFF', fill_type='solid')

            for col_num, value in enumerate(row, 1):
                cell = ws.cell(row=row_num, column=col_num, value=value)
                cell.font = data_font
                cell.alignment = data_alignment
                cell.border = border
                cell.fill = row_fill

                # Apply data type specific formatting
                column_name = str(headers[col_num-1])  # Ensure column name is string
                DataLoader._format_cell_value(cell, value, column_name)

        # Auto-adjust column widths
        for col_num, header in enumerate(headers, 1):
            column_letter = get_column_letter(col_num)
            max_length = max(
                len(str(header)),
                max([len(str(row[col_num-1])) for row in df.itertuples(index=False)] + [0])
            )
            adjusted_width = min(max_length + 2, 50)  # Cap at 50 characters
            ws.column_dimensions[column_letter].width = adjusted_width

        # Freeze header row
        ws.freeze_panes = 'A5'

        # Add auto-filter
        if len(df) > 0:
            ws.auto_filter.ref = f"A4:{get_column_letter(len(headers))}4"

    @staticmethod
    def _format_cell_value(cell, value, column_name: str):
        """Apply appropriate formatting based on data type and column name."""
        from openpyxl.styles import NamedStyle

        if pd.isna(value):
            return

        # IMEI formatting - treat as text, no commas
        if 'imei' in column_name.lower():
            cell.value = str(value).replace(',', '')
            cell.number_format = '@'  # Text format
            return

        # Date formatting
        if 'date' in column_name.lower() or 'Date' in column_name:
            try:
                if isinstance(value, str):
                    # Try to parse string dates
                    cell.value = pd.to_datetime(value).date()
                cell.number_format = 'YYYY-MM-DD'
            except:
                pass

        # Currency formatting
        elif any(keyword in column_name.lower() for keyword in ['price', 'amount', 'incentive', 'margin', 'cost', 'total']):
            try:
                if isinstance(value, (int, float)):
                    cell.number_format = '₹#,##0.00'
            except:
                pass

        # Number formatting
        elif isinstance(value, (int, float)):
            if value == int(value):
                cell.number_format = '#,##0'
            else:
                cell.number_format = '#,##0.00'