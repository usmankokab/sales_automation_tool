import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import Optional, Tuple
import os
import logging
from datetime import datetime

# Set up logging for dashboard
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('siat_dashboard.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('siat_dashboard')

from src.data.loader import DataLoader
from src.calculations.engine import CalculationEngine

class SIATDashboard:
    """Professional Streamlit-based dashboard for SIAT application."""

    def __init__(self):
        st.set_page_config(
            page_title="SIAT - Sales & Incentive Automation Tool",
            page_icon="💰",
            layout="wide",
            initial_sidebar_state="expanded"
        )

        # Custom CSS for professional look
        st.markdown("""
        <style>
        .main-header {
            font-size: 2.5rem;
            font-weight: bold;
            color: #1f77b4;
            text-align: center;
            margin-bottom: 2rem;
        }
        .metric-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 10px;
            padding: 20px;
            color: white;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .metric-value {
            font-size: 2rem;
            font-weight: bold;
            margin: 10px 0;
        }
        .metric-label {
            font-size: 1rem;
            opacity: 0.9;
        }
        .sidebar-header {
            color: #1f77b4;
            font-size: 1.2rem;
            font-weight: bold;
            margin-bottom: 1rem;
        }
        /* Hide specific menu items: Deploy button */
        button[kind="header"] {display: none;}
        /* Hide Auto Rerun menu item */
        button[data-testid="stMainMenuItem-autoRerun"] {display: none !important;}
        footer {visibility: hidden;}
        </style>
        
        <script>
        // Hide Rerun menu item
        const hideRerunMenuItem = () => {
            const menuItems = document.querySelectorAll('[data-testid="stMainMenuItem"]');
            menuItems.forEach(item => {
                const label = item.querySelector('[data-testid="stMainMenuItemLabel"]');
                if (label && label.textContent.trim() === 'Rerun') {
                    item.style.display = 'none';
                }
            });
        };
        
        // Run on load and observe for changes
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', hideRerunMenuItem);
        } else {
            hideRerunMenuItem();
        }
        
        // Observe for dynamic menu changes
        const observer = new MutationObserver(hideRerunMenuItem);
        observer.observe(document.body, { childList: true, subtree: true });
        </script>
        """, unsafe_allow_html=True)

        self.data_loader = DataLoader()

        # Initialize session state for data persistence
        if 'calculation_engine' not in st.session_state:
            st.session_state.calculation_engine = None
        if 'processed_data' not in st.session_state:
            st.session_state.processed_data = None
        if 'pivot_data' not in st.session_state:
            st.session_state.pivot_data = None
        if 'workbook_data' not in st.session_state:
            st.session_state.workbook_data = None
        if 'temp_workbook_path' not in st.session_state:
            st.session_state.temp_workbook_path = None
        if 'temp_files_to_cleanup' not in st.session_state:
            st.session_state.temp_files_to_cleanup = []

        # Use session state instead of instance variables
        self.calculation_engine = st.session_state.calculation_engine
        self.processed_data = st.session_state.processed_data
        self.pivot_data = st.session_state.pivot_data
        self.workbook_data = st.session_state.workbook_data
        self.temp_workbook_path = st.session_state.temp_workbook_path

        # Clean up any leftover temp files from previous sessions
        self._cleanup_temp_files()

    def _cleanup_temp_files(self):
        """Safely clean up temporary files."""
        files_to_remove = []
        for temp_file in st.session_state.temp_files_to_cleanup:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    logger.info(f"Cleaned up temp file: {temp_file}")
                    files_to_remove.append(temp_file)
            except PermissionError:
                logger.warning(f"Could not delete temp file (still in use): {temp_file}")
            except Exception as e:
                logger.error(f"Error deleting temp file {temp_file}: {e}")

        # Remove successfully deleted files from the list
        for file in files_to_remove:
            st.session_state.temp_files_to_cleanup.remove(file)

    def run(self):
        """Main dashboard application."""
        self._setup_sidebar()

        # Main content
        st.markdown('<div class="main-header">💰 Sales & Incentive Automation Tool</div>', unsafe_allow_html=True)
        st.markdown('<p style="text-align: center; font-style: italic;">Automating mobile phone sales reconciliation and incentive calculations</p>', unsafe_allow_html=True)
        st.markdown("---")

        # Display results if data has been processed
        if st.session_state.processed_data is not None and not st.session_state.processed_data.empty:
            self._display_overview_metrics()
            self._display_charts()
            self._display_data_tables()
            self._display_error_log()
        
    def _setup_sidebar(self):
        """Setup professional sidebar with workbook upload and controls."""
        st.sidebar.markdown('<div class="sidebar-header">🏷️ Brand Selection</div>', unsafe_allow_html=True)
        
        # Brand dropdown
        brand_options = [
            "Select Brand",
            "Oppo",
            "Samsung",
            "Realme",
            "Redmi",
            "Vivo",
            "Techno",
            "Itel",
            "Motorola",
            "Poco"
        ]
        
        selected_brand = st.sidebar.selectbox(
            "Select Brand",
            brand_options,
            key="brand_selector",
            help="Select the brand before uploading the workbook"
        )
        
        # Store selected brand in session state
        if 'selected_brand' not in st.session_state:
            st.session_state.selected_brand = "Select Brand"
        
        if selected_brand != st.session_state.selected_brand:
            st.session_state.selected_brand = selected_brand
        
        st.sidebar.markdown("---")
        st.sidebar.markdown('<div class="sidebar-header">📊 Workbook Upload</div>', unsafe_allow_html=True)

        # Check if brand is selected
        if st.session_state.selected_brand == "Select Brand":
            st.sidebar.warning("⚠️ Please select a brand first")
            return

        # Single workbook uploader
        self.workbook_file = st.sidebar.file_uploader(
            "Upload SIAT Workbook",
            type=['xlsx', 'xls'],
            help="Upload the complete Excel workbook containing all sheets: Sales, Scheme, Drop Dump, Price List",
            key="workbook_uploader"
        )

        if self.workbook_file is not None:
            # Validate brand match with filename
            filename = self.workbook_file.name.lower()
            brand_name = st.session_state.selected_brand.lower()
            
            # Handle brand name variations
            brand_match = False
            
            if brand_name == "realme":
                # Check for variations: realme, real me, real-me, etc.
                if any(variant in filename for variant in ["realme", "real me", "real-me", "real_me"]):
                    brand_match = True
            else:
                # Standard case-insensitive check for other brands
                if brand_name in filename:
                    brand_match = True
            
            if not brand_match:
                st.sidebar.error(f"❌ Brand does not match. Please upload a correct file for {st.session_state.selected_brand}")
                st.sidebar.warning(f"Expected filename to contain: '{st.session_state.selected_brand}'")
                return
            else:
                st.sidebar.success(f"✅ Brand matched: {st.session_state.selected_brand}")
            
            st.sidebar.success("✅ Workbook uploaded successfully!")

            # Save uploaded file to temporary location
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
                tmp_file.write(self.workbook_file.getvalue())
                self.temp_workbook_path = tmp_file.name
                st.session_state.temp_workbook_path = self.temp_workbook_path
                st.session_state.temp_files_to_cleanup.append(self.temp_workbook_path)

            # Display workbook info
            st.sidebar.markdown("### 📋 Workbook Contents")
            try:
                workbook_data = self.data_loader.load_workbook(self.temp_workbook_path)
                for sheet_name, df in workbook_data.items():
                    st.sidebar.write(f"• **{sheet_name.title()}**: {df.shape[0]} rows, {df.shape[1]} columns")

                # Extract data sources for processing
                self.sales_data, self.price_list, self.scheme_file, self.drop_dump = \
                    self.data_loader.extract_data_sources(workbook_data)

                # Save extracted data to session state
                st.session_state.workbook_data = workbook_data

                logger.info(f"Data extracted - sales: {self.sales_data.shape if self.sales_data is not None else None}, " +
                           f"price: {self.price_list.shape if self.price_list is not None else None}, " +
                           f"scheme: {self.scheme_file.shape if self.scheme_file is not None else None}, " +
                           f"drop: {self.drop_dump.shape if self.drop_dump is not None else None}")

                st.sidebar.markdown("---")

                if st.sidebar.button("🚀 Process Calculations", type="primary", use_container_width=True):
                    # Processing status container
                    status_container = st.sidebar.container()

                    with status_container:
                        st.write("🔄 **Processing Status:**")
                        progress_bar = st.progress(0)
                        status_text = st.empty()

                        status_text.text("Starting calculations...")
                        progress_bar.progress(10)

                        # Process data
                        success = self._process_data_with_status(status_text, progress_bar)

                        if success:
                            progress_bar.progress(100)
                            status_text.text("✅ Processing completed!")
                        else:
                            progress_bar.progress(0)
                            status_text.text("❌ Processing failed")

            except Exception as e:
                logger.error(f"Error reading workbook: {str(e)}")
                # Clean up temp files safely
                self._cleanup_temp_files()

            # Debug information (outside try-except)
            if st.sidebar.checkbox("🔍 Show Debug Info", help="Show detailed information about loaded data"):
                self._show_debug_info()

            # Download processed results
            if self.processed_data is not None:
                st.sidebar.markdown("### 💾 Export Results")
                self._create_download_button()

                # Cleanup temp files button
                if st.sidebar.button("🧹 Cleanup Temp Files", help="Remove temporary files created during processing"):
                    self._cleanup_temp_files()
                    st.sidebar.success("✅ Temp files cleaned up")

    def _show_debug_info(self):
        """Show debug information about loaded data."""
        st.sidebar.markdown("### 🔍 Debug Info")
        for attr, label in [('sales_data', 'Sales'), ('price_list', 'Price List'),
                             ('scheme_file', 'Scheme'), ('drop_dump', 'Drop Dump')]:
            df = getattr(self, attr, None)
            if df is not None:
                st.sidebar.write(f"**{label}**: {df.shape[0]} rows × {df.shape[1]} cols")
            else:
                st.sidebar.write(f"**{label}**: Not loaded")

    def _process_data_with_status(self, status_text, progress_bar):
        """Process data with status updates."""
        try:
            logger.info("Starting _process_data_with_status")

            # Check if data is available (should be loaded in sidebar)
            if (not hasattr(self, 'sales_data') or self.sales_data is None or
                not hasattr(self, 'price_list') or self.price_list is None or
                not hasattr(self, 'scheme_file') or self.scheme_file is None or
                not hasattr(self, 'drop_dump') or self.drop_dump is None):
                logger.error("Required data not available for processing")
                status_text.text("❌ Data not loaded. Please upload and process a workbook first.")
                progress_bar.progress(0)
                return False

            status_text.text("Data validation complete...")
            progress_bar.progress(20)
            logger.info("Data availability confirmed")

            status_text.text("Initializing calculation engine...")
            progress_bar.progress(40)
            logger.info("Starting calculation engine initialization...")

            logger.info(f"Data sizes: sales={self.sales_data.shape if self.sales_data is not None else None}, " +
                       f"price={self.price_list.shape if self.price_list is not None else None}, " +
                       f"scheme={self.scheme_file.shape if self.scheme_file is not None else None}, " +
                       f"drop={self.drop_dump.shape if self.drop_dump is not None else None}")

            self.calculation_engine = CalculationEngine(
                self.drop_dump, self.price_list,
                self.scheme_file, self.sales_data
            )
            logger.info("Calculation engine initialized successfully")

            status_text.text("Running calculations...")
            progress_bar.progress(60)
            logger.info("Running calculations...")

            self.processed_data, errors = self.calculation_engine.run_calculations()
            logger.info(f"Calculations completed, processed {len(self.processed_data) if self.processed_data is not None else 0} records")

            status_text.text("Generating reports...")
            progress_bar.progress(80)

            if errors:
                error_count = len([e for e in errors if 'Warning' not in e])
                warning_count = len([e for e in errors if 'Warning' in e])

                if error_count > 0:
                    with st.expander(f"❌ {error_count} Errors Found (Click to expand)", expanded=True):
                        st.error("The following errors occurred during processing:")
                        for i, error in enumerate(errors, 1):
                            if 'Warning' not in error:
                                st.error(f"{i}. {error}")
                        st.info("💡 **Note:** Errors may prevent some calculations. Check your data and try again.")

                if warning_count > 0:
                    with st.expander(f"⚠️ {warning_count} Warnings (Click to expand)", expanded=False):
                        st.warning("The following warnings were generated:")
                        for i, error in enumerate(errors, 1):
                            if 'Warning' in error:
                                st.warning(f"{i}. {error}")
                        st.info("⚠️ Warnings indicate potential data issues but processing continues.")

            if self.processed_data is not None and not self.processed_data.empty:
                try:
                    self.pivot_data = self.calculation_engine.generate_distributor_pivot_report()

                    # Save to session state
                    st.session_state.calculation_engine = self.calculation_engine
                    st.session_state.processed_data = self.processed_data
                    st.session_state.pivot_data = self.pivot_data

                    # Success message with details
                    st.success(f"✅ **Processing Complete!** Successfully processed {len(self.processed_data)} records")
                    if self.pivot_data is not None:
                        st.info(f"📊 Generated distributor pivot for {len(self.pivot_data)} distributors")
                    else:
                        st.info("📊 Pivot report generation failed")

                    # Force a rerun to show results
                    st.rerun()

                except Exception as e:
                    logger.error(f"Failed to generate pivot report: {str(e)}")
                    st.warning(f"⚠️ Report generation failed: {str(e)}")
                    # Still save processed data even if pivot fails
                    st.session_state.processed_data = self.processed_data
                    st.session_state.pivot_data = None
                    st.success(f"✅ **Processing Complete!** Successfully processed {len(self.processed_data)} records")
                    st.info("📊 Basic results available (pivot report failed)")
                    st.rerun()
            else:
                logger.error("Processed data is None or empty")
                st.error("❌ Processing completed but no valid results were generated")
                return False

        except Exception as e:
            st.error(f"❌ Processing failed: {str(e)}")
            import traceback
            st.error(f"Full error details: {traceback.format_exc()}")

    def _generate_enhanced_pivot(self) -> pd.DataFrame:
        """Generate enhanced pivot report from processed data."""
        logger.info(f"Checking processed_data availability: hasattr={hasattr(st.session_state, 'processed_data')}")

        if hasattr(st.session_state, 'processed_data'):
            logger.info(f"processed_data is None: {st.session_state.processed_data is None}")
            if st.session_state.processed_data is not None:
                logger.info(f"processed_data is empty: {st.session_state.processed_data.empty}")
                logger.info(f"processed_data shape: {st.session_state.processed_data.shape}")

        if (not hasattr(st.session_state, 'processed_data') or
            st.session_state.processed_data is None or
            st.session_state.processed_data.empty):
            logger.warning("No processed data available for pivot generation")
            return None

        try:
            logger.info("Generating pivot report...")

            # Check if required columns exist
            required_columns = ['total schme rcvd', 'nt nlc (o-ac)', 'final price (g-k)', 'distibutor']
            missing_columns = [col for col in required_columns if col not in st.session_state.processed_data.columns]

            if missing_columns:
                logger.error(f"Missing required columns for pivot: {missing_columns}")
                available_value_cols = [col for col in ['total schme rcvd', 'nt nlc (o-ac)', 'final price (g-k)']
                                       if col in st.session_state.processed_data.columns]
                available_index_cols = [col for col in ['distibutor', 'master modal']
                                       if col in st.session_state.processed_data.columns]

                if not available_value_cols:
                    logger.error("No value columns available for pivot")
                    return None

                pivot = pd.pivot_table(
                    st.session_state.processed_data,
                    values=available_value_cols,
                    index=available_index_cols if available_index_cols else None,
                    aggfunc='sum'
                ).reset_index()

            else:
                # Use the final column names from processed data
                pivot = pd.pivot_table(
                    st.session_state.processed_data,
                    values=['total schme rcvd', 'nt nlc (o-ac)', 'final price (g-k)'],
                    index=['distibutor'],
                    aggfunc='sum'
                ).reset_index()

            if pivot is not None and not pivot.empty:
                if 'final price (g-k)' in pivot.columns and 'nt nlc (o-ac)' in pivot.columns:
                    pivot['Total_Margin'] = pivot['final price (g-k)'] - pivot['nt nlc (o-ac)']

                column_rename_map = {
                    'total schme rcvd': 'Total_Incentives',
                    'nt nlc (o-ac)': 'Total_NLC',
                    'final price (g-k)': 'Total_Final_Price',
                    'distibutor': 'Distributor',
                    'master modal': 'Model'
                }

                pivot = pivot.rename(columns=column_rename_map)

                logger.info(f"Generated pivot report with {len(pivot)} entries")
                return pivot
            else:
                logger.warning("Pivot table is empty")
                return None

        except Exception as e:
            logger.error(f"Error generating pivot report: {str(e)}")
            logger.error(f"Processed data shape: {st.session_state.processed_data.shape}")
            logger.error(f"Processed data columns: {list(st.session_state.processed_data.columns)}")
            return None
    
    def _display_overview_metrics(self):
        """Display professional key performance metrics."""
        if st.session_state.processed_data is None or st.session_state.processed_data.empty:
            return

        st.header("📊 Executive Summary")

        # Calculate metrics using final column names
        total_incentive = st.session_state.processed_data['total schme rcvd'].sum()
        total_nlc = st.session_state.processed_data['TOTAL PCT SCHEME + FALT PAYOUT'].sum()
        total_margin = (st.session_state.processed_data['FINAL PRICE FOR CALCULATION'] - st.session_state.processed_data['TOTAL PCT SCHEME + FALT PAYOUT']).sum()
        total_final_price = st.session_state.processed_data['FINAL PRICE FOR CALCULATION'].sum()
        total_records = len(st.session_state.processed_data)
        avg_margin_pct = (total_margin / total_final_price * 100) if total_final_price > 0 else 0
        drops_count = (st.session_state.processed_data['drop'] != 0).sum()
        drops_value = st.session_state.processed_data['drop'].sum()

        # Display metrics in a professional grid
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">💰 Total Incentives</div>
                <div class="metric-value">₹{total_incentive:,.0f}</div>
                <div>Recovery Amount</div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">🏢 Net Landing Cost</div>
                <div class="metric-value">₹{total_nlc:,.0f}</div>
                <div>After Incentives</div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">📈 Total Margin</div>
                <div class="metric-value">{avg_margin_pct:.1f}%</div>
                <div>₹{total_margin:,.0f} earned</div>
            </div>
            """, unsafe_allow_html=True)

        with col4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">📊 Transactions</div>
                <div class="metric-value">{total_records:,}</div>
                <div>{drops_count} with drops</div>
            </div>
            """, unsafe_allow_html=True)

        # Additional insights
        st.markdown("---")
        col1, col2, col3 = st.columns(3)

        with col1:
            st.info(f"🔻 **Drop Impact**: ₹{drops_value:,.0f} total drop value across {drops_count} devices")

        with col2:
            successful_matches = st.session_state.processed_data['MOP AT THE TIME OF PURCHASE'].notna().sum()
            match_rate = (successful_matches / total_records * 100) if total_records > 0 else 0
            st.info(f"✅ **Price Match Rate**: {match_rate:.1f}% ({successful_matches}/{total_records})")

        with col3:
            avg_incentive_per_device = total_incentive / total_records if total_records > 0 else 0
            st.info(f"🎯 **Avg Incentive/Device**: ₹{avg_incentive_per_device:,.0f}")
    
    def _display_charts(self):
        """Display professional interactive charts and visualizations."""
        if st.session_state.processed_data is None or st.session_state.processed_data.empty:
            return

        st.header("📈 Advanced Analytics")

        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "💰 Incentive Analysis",
            "📉 Margin Analysis",
            "📈 Performance Trends",
            "🏢 Distributor Insights",
            "🔍 Data Quality"
        ])

        with tab1:
            self._incentive_analysis_charts()

        with tab2:
            self._margin_analysis_charts()

        with tab3:
            self._performance_trends_charts()

        with tab4:
            self._distributor_insights_charts()

        with tab5:
            self._data_quality_charts()
    
    def _incentive_analysis_charts(self):
        """Comprehensive incentive analysis charts."""
        col1, col2 = st.columns(2)

        with col1:
            # Incentive distribution
            fig = px.histogram(
                st.session_state.processed_data,
                x='total schme rcvd',
                nbins=30,
                title="Incentive Distribution",
                labels={'total schme rcvd': 'Total Incentive'},
                color_discrete_sequence=['#1f77b4']
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Calculate incentive breakdown from available data
            # Since we don't have Total_Pct_Incentive/Total_Flat_Incentive in final output,
            # we'll calculate approximate breakdown based on scheme columns
            pct_incentives = 0
            flat_incentives = 0

            # Sum all percentage scheme amounts
            pct_cols = ['amount pct sceme -1', 'amount pct sceme -2', 'amount pct sceme -3', 'amount pct sceme -4']
            for col in pct_cols:
                if col in st.session_state.processed_data.columns:
                    pct_incentives += st.session_state.processed_data[col].sum()

            # Get flat payout
            if 'Flat Payout' in st.session_state.processed_data.columns:
                flat_incentives = st.session_state.processed_data['Flat Payout'].sum()

            incentive_breakdown = pd.DataFrame({
                'Type': ['Percentage Incentives', 'Flat Incentives'],
                'Amount': [pct_incentives, flat_incentives]
            })

            fig = px.pie(
                incentive_breakdown,
                values='Amount',
                names='Type',
                title="Incentive Type Breakdown",
                color_discrete_sequence=['#ff7f0e', '#2ca02c']
            )
            st.plotly_chart(fig, use_container_width=True)

        # Incentive vs Price scatter
            fig = px.scatter(
                st.session_state.processed_data,
                x='MOP AT THE TIME OF PURCHASE',
                y='total schme rcvd',
                title="Incentive vs Device Price",
                labels={
                    'MOP AT THE TIME OF PURCHASE': 'Device Price',
                    'total schme rcvd': 'Total Incentive'
                },
                trendline="ols",
                color_discrete_sequence=['#d62728']
            )
        st.plotly_chart(fig, use_container_width=True)
    
    def _margin_analysis_charts(self):
        """Comprehensive margin analysis charts."""
        col1, col2 = st.columns(2)

        with col1:
            # Price vs NLC scatter
            fig = px.scatter(
                st.session_state.processed_data,
                x='MOP AT THE TIME OF PURCHASE',
                y='TOTAL PCT SCHEME + FALT PAYOUT',
                title="Price vs Net Landing Cost",
                labels={
                    'MOP AT THE TIME OF PURCHASE': 'Device Price (₹)',
                    'TOTAL PCT SCHEME + FALT PAYOUT': 'Net Landing Cost (₹)'
                },
                trendline="ols",
                color='drop',
                color_continuous_scale='RdYlGn_r'
            )
            fig.update_layout(legend_title_text='Has Drop')
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Margin distribution (calculated as final price - NLC)
            margin_data = st.session_state.processed_data['FINAL PRICE FOR CALCULATION'] - st.session_state.processed_data['TOTAL PCT SCHEME + FALT PAYOUT']
            fig = px.histogram(
                x=margin_data,
                nbins=30,
                title="Margin Distribution",
                labels={'x': 'Margin (₹)'},
                color_discrete_sequence=['#2ca02c']
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        # Margin percentage by distributor (not model, since pivot is by distributor)
        if st.session_state.pivot_data is not None and 'Total_Margin' in st.session_state.pivot_data.columns:
            # Calculate margin percentage
            pivot_with_pct = st.session_state.pivot_data.copy()
            pivot_with_pct['Margin_Percentage'] = (pivot_with_pct['Total_Margin'] / pivot_with_pct['Total_Final_Price'] * 100).fillna(0)
            
            fig = px.bar(
                pivot_with_pct,
                x='Distributor',
                y='Margin_Percentage',
                title="Margin Percentage by Distributor",
                labels={
                    'Distributor': 'Distributor',
                    'Margin_Percentage': 'Margin %'
                },
                color_discrete_sequence=['#9467bd']
            )
            fig.update_xaxes(tickangle=45)
            st.plotly_chart(fig, use_container_width=True)
    
    def _performance_trends_charts(self):
        """Performance trends and time-series analysis."""
        if 'sell out date' in st.session_state.processed_data.columns:
            df_trends = st.session_state.processed_data.copy()
            df_trends['Month'] = pd.to_datetime(df_trends['sell out date']).dt.to_period('M').dt.to_timestamp()

            col1, col2 = st.columns(2)

            with col1:
                monthly_incentives = df_trends.groupby('Month')['total schme rcvd'].sum().reset_index()
                fig = px.line(
                        monthly_incentives,
                        x='Month',
                        y='total schme rcvd',
                        title="Monthly Incentive Trends",
                        labels={'Month': 'Month', 'total schme rcvd': 'Total Incentives'},
                        markers=True
                    )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                monthly_volume = df_trends.groupby('Month').size().reset_index(name='Transactions')
                fig = px.bar(
                    monthly_volume,
                    x='Month',
                    y='Transactions',
                    title="Monthly Transaction Volume",
                    labels={'Month': 'Month', 'Transactions': 'Number of Transactions'}
                )
                st.plotly_chart(fig, use_container_width=True)

            monthly_avg = df_trends.groupby('Month')['total schme rcvd'].mean().reset_index()
            fig = px.area(
                monthly_avg,
                x='Month',
                y='total schme rcvd',
                title="Average Incentive per Transaction",
                labels={'Month': 'Month', 'total schme rcvd': 'Avg Incentive'},
                color_discrete_sequence=['#17becf']
            )
            st.plotly_chart(fig, use_container_width=True)

    def _distributor_insights_charts(self):
        """Comprehensive distributor performance analysis."""
        if st.session_state.pivot_data is not None:
            col1, col2 = st.columns(2)

            with col1:
                fig = px.bar(
                    st.session_state.pivot_data,
                    x='Distributor Name',
                    y='Scheme Total Amt',
                    title="Scheme Amount by Distributor",
                    labels={
                        'Distributor Name': 'Distributor',
                        'Scheme Total Amt': 'Total Scheme Amount (₹)'
                    },
                    color='Scheme Total Amt',
                    color_continuous_scale='Viridis'
                )
                fig.update_xaxes(tickangle=45)
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                fig = px.scatter(
                    st.session_state.pivot_data,
                    x='Scheme Total Amt',
                    y='Net Amt Rec',
                    size='Diff',
                    title="Distributor Scheme vs Net Amount",
                    labels={
                        'Scheme Total Amt': 'Scheme Amount',
                        'Net Amt Rec': 'Net Amount Received',
                        'Diff': 'Difference'
                    },
                    color='Distributor Name',
                    hover_name='Distributor Name'
                )
                st.plotly_chart(fig, use_container_width=True)

            # Top models by incentive (from raw data)
            if 'master model' in st.session_state.processed_data.columns and 'total schme rcvd' in st.session_state.processed_data.columns:
                model_incentives = st.session_state.processed_data.groupby('master model')['total schme rcvd'].sum().nlargest(10).reset_index()
                model_incentives.columns = ['Model', 'Total_Incentives']
                
                fig = px.bar(
                    model_incentives,
                    x='Model',
                    y='Total_Incentives',
                    title="Top 10 Models by Incentive Value",
                    labels={
                        'Model': 'Device Model',
                        'Total_Incentives': 'Total Incentives (₹)'
                    },
                    color_discrete_sequence=['#e377c2']
                )
                fig.update_xaxes(tickangle=45)
                st.plotly_chart(fig, use_container_width=True)

    def _data_quality_charts(self):
        """Data quality and validation insights."""
        # Create processing status based on data completeness
        def assess_record_status(row):
            if pd.isna(row.get('master model', '')) or pd.isna(row.get('sell out date')):
                return 'Incomplete'
            elif pd.isna(row.get('MOP AT THE TIME OF PURCHASE')):
                return 'Price Missing'
            else:
                return 'Complete'

        status_series = self.processed_data.apply(assess_record_status, axis=1)
        status_counts = status_series.value_counts().reset_index()
        status_counts.columns = ['Status', 'Count']

        col1, col2 = st.columns(2)

        with col1:
            fig = px.pie(
                status_counts,
                values='Count',
                names='Status',
                title="Data Processing Status",
                color_discrete_sequence=['#2ca02c', '#d62728', '#ff7f0e']
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Price match success rate
            price_match_status = pd.DataFrame({
                'Status': ['Price Matched', 'Price Missing'],
                'Count': [
                    st.session_state.processed_data['MOP AT THE TIME OF PURCHASE'].notna().sum(),
                    st.session_state.processed_data['MOP AT THE TIME OF PURCHASE'].isna().sum()
                ]
            })

            fig = px.pie(
                price_match_status,
                values='Count',
                names='Status',
                title="Price Matching Success Rate",
                color_discrete_sequence=['#1f77b4', '#d62728']
            )
            st.plotly_chart(fig, use_container_width=True)

        # Data completeness radar chart
        completeness_data = pd.DataFrame({
            'Field': ['IMEI', 'Master Model', 'Sell Out Date', 'MOP AT THE TIME OF PURCHASE', 'Distributor'],
            'Completeness': [
                st.session_state.processed_data['IMEI'].notna().mean() * 100,
                st.session_state.processed_data['master model'].notna().mean() * 100,
                st.session_state.processed_data['sell out date'].notna().mean() * 100,
                st.session_state.processed_data['MOP AT THE TIME OF PURCHASE'].notna().mean() * 100,
                st.session_state.processed_data['distibutor'].notna().mean() * 100,
            ]
        })

        fig = px.line_polar(
            completeness_data,
            r='Completeness',
            theta='Field',
            line_close=True,
            title="Data Completeness Radar"
        )
        fig.update_traces(fill='toself')
        st.plotly_chart(fig, use_container_width=True)
    
    def _display_data_tables(self):
        """Display professional data tables and pivot reports."""
        if st.session_state.processed_data is None or st.session_state.processed_data.empty:
            return

        st.header("📋 Detailed Reports")

        tab1, tab2, tab3 = st.tabs(["📊 Processed Transactions", "🏢 Distributor Summary", "📈 Model Performance"])

        with tab1:
            st.subheader("Processed Transaction Data")
            st.markdown("*Complete dataset with all calculations and validations*")

            # Column selector - include key columns by default
            all_columns = st.session_state.processed_data.columns.tolist()
            default_cols = ['IMEI', 'sell out date', 'master model', 'distibutor', 'purchase date', 'purchase price',
                          'MOP AT THE TIME OF PURCHASE', 'FINAL PRICE FOR CALCULATION', 'drop', 'total schme rcvd', 'TOTAL PCT SCHEME + FALT PAYOUT',
                          'Current Month Invoice Price', 'Current Month Pre-GST of Invoice Price']

            selected_cols = st.multiselect(
                "Select columns to display:",
                all_columns,
                default=[col for col in default_cols if col in all_columns],
                key="processed_data_cols"
            )

            # Force rerun when selection changes to ensure table updates
            if selected_cols != st.session_state.get('last_selected_cols', []):
                st.session_state.last_selected_cols = selected_cols
                st.rerun()

            if selected_cols:
                display_df = st.session_state.processed_data[selected_cols].copy()

                # Format numeric columns
                numeric_cols = display_df.select_dtypes(include=[np.number]).columns
                for col in numeric_cols:
                    if col in ['MOP AT THE TIME OF PURCHASE', 'drop', 'total schme rcvd', 'TOTAL PCT SCHEME + FALT PAYOUT', 'FINAL PRICE FOR CALCULATION',
                              'Current Month Invoice Price', 'Current Month Pre-GST of Invoice Price']:
                        display_df[col] = display_df[col].apply(lambda x: f"₹{x:,.0f}" if pd.notna(x) else "N/A")

                st.dataframe(display_df, use_container_width=True, hide_index=True)

                st.info(f"Showing {len(display_df)} of {len(st.session_state.processed_data)} total records")

        with tab2:
            st.subheader("Distributor Pivot Report")
            st.markdown("*Scheme reconciliation by distributor*")

            if st.session_state.pivot_data is not None:
                # Display the pivot data
                st.dataframe(st.session_state.pivot_data, use_container_width=True, hide_index=True)

                # Summary statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Distributors", len(st.session_state.pivot_data))
                with col2:
                    total_scheme = st.session_state.pivot_data['Scheme Total Amt'].sum()
                    st.metric("Total Scheme Amount", f"₹{total_scheme:,.2f}")
                with col3:
                    total_net = st.session_state.pivot_data['Net Amt Rec'].sum()
                    st.metric("Total Net Amount", f"₹{total_net:,.2f}")

        with tab3:
            st.subheader("Model Performance Analysis")
            st.markdown("*Performance metrics by device model*")

            if st.session_state.processed_data is not None:
                model_summary = st.session_state.processed_data.groupby('master model').agg({
                    'total schme rcvd': 'sum',
                    'TOTAL PCT SCHEME + FALT PAYOUT': 'sum',
                    'FINAL PRICE FOR CALCULATION': 'sum'
                }).reset_index()
                model_summary.columns = ['Model', 'Total_Incentives', 'Total_NLC', 'Total_Final_Price']
                model_summary['Total_Margin'] = model_summary['Total_Final_Price'] - model_summary['Total_NLC']
                model_summary = model_summary.sort_values('Total_Incentives', ascending=False)
                
                # Format for display
                display_model = model_summary.copy()
                for col in ['Total_Incentives', 'Total_NLC', 'Total_Final_Price', 'Total_Margin']:
                    if col in display_model.columns:
                        display_model[col] = display_model[col].apply(lambda x: f"₹{x:,.2f}")
                st.dataframe(display_model, use_container_width=True, hide_index=True)

    def _create_download_button(self):
        """Create download button for processed results."""
        if st.session_state.processed_data is not None and st.session_state.temp_workbook_path is not None:
            try:
                # Save results to the output folder
                output_file = self.data_loader.save_results_to_workbook(
                    st.session_state.temp_workbook_path,
                    st.session_state.processed_data,
                    st.session_state.pivot_data
                )

                st.sidebar.success(f"✅ Results saved to: output/{os.path.basename(output_file)}")

                with open(output_file, 'rb') as f:
                    file_data = f.read()

                st.sidebar.download_button(
                    label="📥 Download Professional Excel Report",
                    data=file_data,
                    file_name=os.path.basename(output_file),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    help="Download beautifully formatted Excel report with multiple sheets"
                )

            except Exception as e:
                st.sidebar.error(f"Error saving results: {str(e)}")
                st.sidebar.info("Results are saved in the 'output' folder on the server.")
    
    def _display_error_log(self):
        """Display professional error logs and validation results."""
        if st.session_state.calculation_engine is None:
            return

        st.header("🔍 Processing Summary & Validation")

        validation_errors = self.calculation_engine.validate_data_integrity()
        processing_errors = self.calculation_engine.errors

        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            error_count = len([e for e in processing_errors + validation_errors if 'Warning' not in e.lower()])
            st.metric("Errors", error_count, delta="-" if error_count == 0 else None)

        with col2:
            warning_count = len([e for e in processing_errors + validation_errors if 'warning' in e.lower()])
            st.metric("Warnings", warning_count)

        with col3:
            # Calculate success based on data completeness
            complete_records = len(st.session_state.processed_data[
                (st.session_state.processed_data['master model'].notna()) &
                (st.session_state.processed_data['sell out date'].notna()) &
                (st.session_state.processed_data['MOP AT THE TIME OF PURCHASE'].notna())
            ])
            st.metric("Successful", complete_records)

        with col4:
            total_processed = len(st.session_state.processed_data)
            st.metric("Total Processed", total_processed)

        # Detailed logs
        if validation_errors or processing_errors:
            with st.expander("📋 Detailed Logs", expanded=False):
                if processing_errors:
                    st.subheader("⚠️ Processing Issues")
                    for i, error in enumerate(processing_errors, 1):
                        if 'warning' in error.lower():
                            st.warning(f"{i}. {error}")
                        else:
                            st.error(f"{i}. {error}")

                if validation_errors:
                    st.subheader("🔍 Validation Results")
                    for i, error in enumerate(validation_errors, 1):
                        if 'warning' in error.lower():
                            st.warning(f"{i}. {error}")
                        else:
                            st.error(f"{i}. {error}")

            # Error summary table
            # Calculate successful records based on data completeness
            successful_records = len(st.session_state.processed_data[
                (st.session_state.processed_data['master model'].notna()) &
                (st.session_state.processed_data['sell out date'].notna()) &
                (st.session_state.processed_data['MOP AT THE TIME OF PURCHASE'].notna())
            ])

            error_summary = pd.DataFrame({
                'Category': ['Processing Errors', 'Validation Warnings', 'Successful Records'],
                'Count': [
                    len([e for e in processing_errors if 'warning' not in e.lower()]),
                    len([e for e in validation_errors if 'warning' in e.lower()]),
                    successful_records
                ]
            })

            st.subheader("📊 Error Summary")
            st.dataframe(error_summary, use_container_width=True, hide_index=True)

        else:
            st.success("✅ **All calculations completed successfully with no errors!**")
            st.balloons()

        # Data quality score
        st.subheader("⭐ Data Quality Score")
        completeness_score = (
            st.session_state.processed_data['MOP AT THE TIME OF PURCHASE'].notna().mean() +
            st.session_state.processed_data['master model'].notna().mean() +
            st.session_state.processed_data['sell out date'].notna().mean()
        ) / 3 * 100

        if completeness_score >= 95:
            st.success(f"Excellent: {completeness_score:.1f}% data quality")
        elif completeness_score >= 85:
            st.info(f"Good: {completeness_score:.1f}% data quality")
        else:
            st.warning(f"Needs attention: {completeness_score:.1f}% data quality")

def main():
    """Main entry point for the dashboard."""
    dashboard = SIATDashboard()
    dashboard.run()

if __name__ == "__main__":
    main()