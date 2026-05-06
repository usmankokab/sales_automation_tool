import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import Optional, Tuple
import os
from datetime import datetime

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
        </style>
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

        # Use session state instead of instance variables
        self.calculation_engine = st.session_state.calculation_engine
        self.processed_data = st.session_state.processed_data
        self.pivot_data = st.session_state.pivot_data
        self.workbook_data = st.session_state.workbook_data
        self.temp_workbook_path = st.session_state.temp_workbook_path

    def run(self):
        """Main dashboard application."""
        self._setup_sidebar()

        # Main content
        st.markdown('<div class="main-header">💰 Sales & Incentive Automation Tool</div>', unsafe_allow_html=True)
        st.markdown("*Automating mobile phone sales reconciliation and incentive calculations*")
        st.markdown("---")

        if self._load_data():
            self._display_overview_metrics()
            self._display_charts()
            self._display_data_tables()
            self._display_error_log()
        
    def _setup_sidebar(self):
        """Setup professional sidebar with workbook upload and controls."""
        st.sidebar.markdown('<div class="sidebar-header">📊 Workbook Upload</div>', unsafe_allow_html=True)

        # Single workbook uploader
        self.workbook_file = st.sidebar.file_uploader(
            "Upload SIAT Workbook",
            type=['xlsx', 'xls'],
            help="Upload the complete Excel workbook containing all sheets: Sales, Scheme, Drop Dump, Price List"
        )

        if self.workbook_file is not None:
            st.sidebar.success("✅ Workbook uploaded successfully!")

            # Save uploaded file to temporary location
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
                tmp_file.write(self.workbook_file.getvalue())
                self.temp_workbook_path = tmp_file.name
                st.session_state.temp_workbook_path = self.temp_workbook_path

            # Display workbook info
            st.sidebar.markdown("### 📋 Workbook Contents")
            try:
                workbook_data = self.data_loader.load_workbook(self.temp_workbook_path)
                for sheet_name, df in workbook_data.items():
                    st.sidebar.write(f"• **{sheet_name.title()}**: {df.shape[0]} rows, {df.shape[1]} columns")

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
                st.sidebar.error(f"❌ Error reading workbook: {str(e)}")
                # Clean up temp file on error
                if hasattr(self, 'temp_workbook_path') and os.path.exists(self.temp_workbook_path):
                    os.unlink(self.temp_workbook_path)

            # Debug information (outside try-except)
            if st.sidebar.checkbox("🔍 Show Debug Info", help="Show detailed information about loaded data"):
                self._show_debug_info()

            # Download processed results
            if self.processed_data is not None:
                st.sidebar.markdown("### 💾 Export Results")
                self._create_download_button()

    def _process_data_with_status(self, status_text, progress_bar):
        """Process data with status updates."""
        try:
            # Load data if not already loaded
            if not hasattr(self, 'sales_data'):
                status_text.text("Loading workbook data...")
                progress_bar.progress(20)
                if not self._load_data():
                    return False

            status_text.text("Running calculations...")
            progress_bar.progress(40)

            self.calculation_engine = CalculationEngine(
                self.drop_dump, self.price_list,
                self.scheme_file, self.sales_data
            )

            self.processed_data, errors = self.calculation_engine.run_calculations()

            status_text.text("Generating reports...")
            progress_bar.progress(80)

            if not self.processed_data.empty:
                self.pivot_data = self._generate_enhanced_pivot()

                # Save to session state
                st.session_state.calculation_engine = self.calculation_engine
                st.session_state.processed_data = self.processed_data
                st.session_state.pivot_data = self.pivot_data

                # Show results summary
                st.success(f"✅ **Processing Complete!** Successfully processed {len(self.processed_data)} records")
                st.info(f"📊 Generated summary for {len(self.pivot_data)} distributors")

                return True

        except Exception as e:
            st.error(f"❌ Processing failed: {str(e)}")
            return False

    def _show_debug_info(self):
        """Show detailed debug information about loaded data."""
        st.sidebar.markdown("### 🔍 Debug Information")

        if hasattr(self, 'workbook_data') and self.workbook_data:
            st.sidebar.write("**Workbook Sheets:**")
            for sheet_name, df in self.workbook_data.items():
                st.sidebar.write(f"• {sheet_name}: {df.shape[0]} rows × {df.shape[1]} cols")

        if hasattr(self, 'sales_data'):
            st.sidebar.write(f"**Sales Data:** {self.sales_data.shape}")
            st.sidebar.write(f"Columns: {list(self.sales_data.columns)[:5]}...")
            if len(self.sales_data) > 0:
                st.sidebar.write(f"Sample IMEI: {self.sales_data['IMEI'].iloc[0]}")
                st.sidebar.write(f"Sample Model: {self.sales_data['Master_Model'].iloc[0]}")

        if hasattr(self, 'drop_dump'):
            st.sidebar.write(f"**Drop Dump:** {self.drop_dump.shape}")
            if len(self.drop_dump) > 0:
                st.sidebar.write(f"Sample IMEI: {self.drop_dump['IMEI'].iloc[0]}")
                if 'Drop_Amount' in self.drop_dump.columns:
                    st.sidebar.write(f"Sample Drop Amount: {self.drop_dump['Drop_Amount'].iloc[0]}")

        if hasattr(self, 'price_list'):
            st.sidebar.write(f"**Price List:** {self.price_list.shape}")
            if len(self.price_list) > 0:
                st.sidebar.write(f"Sample Model: {self.price_list['Master_Model'].iloc[0]}")

        if hasattr(self, 'scheme_file'):
            st.sidebar.write(f"**Scheme File:** {self.scheme_file.shape}")
            if len(self.scheme_file) > 0:
                st.sidebar.write(f"Sample Model: {self.scheme_file['Master_Model'].iloc[0]}")

        else:
            st.sidebar.info("👆 Upload your SIAT workbook to begin analysis")
            st.sidebar.markdown("""
            **Expected Sheets:**
            - `sales` - Transaction data
            - `scheme` - Incentive schemes
            - `drop dump` - Drop amounts
            - `price list` - Pricing information
            """)
    
    def _load_data(self) -> bool:
        """Load and validate uploaded workbook."""
        if not hasattr(self, 'temp_workbook_path') or self.temp_workbook_path is None or not os.path.exists(self.temp_workbook_path):
            return False

        try:
            # Load workbook data
            self.workbook_data = self.data_loader.load_workbook(self.temp_workbook_path)

            # Extract data sources
            self.sales_data, self.price_list, self.scheme_file, self.drop_dump = \
                self.data_loader.extract_data_sources(self.workbook_data)

            # Save workbook data to session state
            st.session_state.workbook_data = self.workbook_data

            st.sidebar.success("✅ All required sheets found and loaded")
            return True

        except Exception as e:
            st.sidebar.error(f"❌ Error processing workbook: {str(e)}")
            import traceback
            st.sidebar.error(f"Details: {traceback.format_exc()}")
            return False
    
    def _process_data(self):
        """Process the loaded data through the calculation engine."""
        # Load data if not already loaded
        if not hasattr(self, 'sales_data'):
            if not self._load_data():
                st.error("❌ Failed to load data. Please check your workbook and try again.")
                return

        try:
            self.calculation_engine = CalculationEngine(
                self.drop_dump, self.price_list,
                self.scheme_file, self.sales_data
            )

            self.processed_data, errors = self.calculation_engine.run_calculations()

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

            if not self.processed_data.empty:
                self.pivot_data = self._generate_enhanced_pivot()

                # Success message with details
                st.success(f"✅ **Processing Complete!** Successfully processed {len(self.processed_data)} records")
                st.info(f"📊 Generated summary for {len(self.pivot_data)} distributors")

                # Force a rerun to show results
                st.rerun()

        except Exception as e:
            st.error(f"❌ Processing failed: {str(e)}")
            import traceback
            st.error(f"Full error details: {traceback.format_exc()}")

    def _generate_enhanced_pivot(self) -> pd.DataFrame:
        """Generate enhanced pivot report with multiple aggregations."""
        if self.processed_data is None:
            return pd.DataFrame()

        pivot = pd.pivot_table(
            self.processed_data,
            values=['Total_Incentive_Received', 'NLC', 'Final_Price', 'Margin', 'Drop_Amount'],
            index=['Distributor', 'Master_Model'],
            aggfunc={
                'Total_Incentive_Received': 'sum',
                'NLC': 'sum',
                'Final_Price': 'sum',
                'Margin': 'sum',
                'Drop_Amount': 'sum'
            },
            fill_value=0
        ).round(2).reset_index()

        # Add percentage calculations
        pivot['Incentive_Percentage'] = (pivot['Total_Incentive_Received'] / pivot['Final_Price'] * 100).round(2)
        pivot['Margin_Percentage'] = (pivot['Margin'] / pivot['Final_Price'] * 100).round(2)

        return pivot
    
    def _display_overview_metrics(self):
        """Display professional key performance metrics."""
        if st.session_state.processed_data is None or st.session_state.processed_data.empty:
            return

        st.header("📊 Executive Summary")

        # Calculate metrics
        total_incentive = st.session_state.processed_data['Total_Incentive_Received'].sum()
        total_nlc = st.session_state.processed_data['NLC'].sum()
        total_margin = st.session_state.processed_data['Margin'].sum()
        total_final_price = st.session_state.processed_data['Final_Price'].sum()
        total_records = len(st.session_state.processed_data)
        avg_margin_pct = (total_margin / total_final_price * 100) if total_final_price > 0 else 0
        drops_count = st.session_state.processed_data['Has_Drop'].sum()
        drops_value = st.session_state.processed_data['Drop_Amount'].sum()

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
            successful_matches = self.processed_data['Matched_Price'].notna().sum()
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
                x='Total_Incentive_Received',
                nbins=30,
                title="Incentive Distribution",
                labels={'Total_Incentive_Received': 'Total Incentive (₹)'},
                color_discrete_sequence=['#1f77b4']
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Incentive breakdown by type
            incentive_breakdown = pd.DataFrame({
                'Type': ['Percentage Incentives', 'Flat Incentives'],
                'Amount': [
                    self.processed_data['Total_Pct_Incentive'].sum(),
                    self.processed_data['Total_Flat_Incentive'].sum()
                ]
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
            x='Matched_Price',
            y='Total_Incentive_Received',
            title="Incentive vs Device Price",
            labels={
                'Matched_Price': 'Device Price (₹)',
                'Total_Incentive_Received': 'Total Incentive (₹)'
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
                x='Matched_Price',
                y='NLC',
                title="Price vs Net Landing Cost",
                labels={
                    'Matched_Price': 'Device Price (₹)',
                    'NLC': 'Net Landing Cost (₹)'
                },
                trendline="ols",
                color='Has_Drop',
                color_discrete_map={True: '#d62728', False: '#1f77b4'}
            )
            fig.update_layout(legend_title_text='Has Drop')
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Margin distribution
            fig = px.histogram(
                st.session_state.processed_data,
                x='Margin',
                nbins=30,
                title="Margin Distribution",
                labels={'Margin': 'Margin (₹)'},
                color_discrete_sequence=['#2ca02c']
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        # Margin percentage by model
        if self.pivot_data is not None:
            fig = px.bar(
                self.pivot_data,
                x='Master_Model',
                y='Margin_Percentage',
                title="Margin Percentage by Model",
                labels={
                    'Master_Model': 'Device Model',
                    'Margin_Percentage': 'Margin %'
                },
                color_discrete_sequence=['#9467bd']
            )
            fig.update_xaxes(tickangle=45)
            st.plotly_chart(fig, use_container_width=True)
    
    def _performance_trends_charts(self):
        """Performance trends and time-series analysis."""
        if 'Sell_Out_Date' in self.processed_data.columns:
            df_trends = self.processed_data.copy()
            df_trends['Month'] = pd.to_datetime(df_trends['Sell_Out_Date']).dt.to_period('M').dt.to_timestamp()

            col1, col2 = st.columns(2)

            with col1:
                # Monthly incentive trends
                monthly_incentives = df_trends.groupby('Month')['Total_Incentive_Received'].sum().reset_index()
                fig = px.line(
                    monthly_incentives,
                    x='Month',
                    y='Total_Incentive_Received',
                    title="Monthly Incentive Trends",
                    labels={
                        'Month': 'Month',
                        'Total_Incentive_Received': 'Total Incentives (₹)'
                    },
                    markers=True
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                # Monthly transaction volume
                monthly_volume = df_trends.groupby('Month').size().reset_index(name='Transactions')
                fig = px.bar(
                    monthly_volume,
                    x='Month',
                    y='Transactions',
                    title="Monthly Transaction Volume",
                    labels={
                        'Month': 'Month',
                        'Transactions': 'Number of Transactions'
                    }
                )
                st.plotly_chart(fig, use_container_width=True)

            # Average incentive per transaction over time
            monthly_avg = df_trends.groupby('Month')['Total_Incentive_Received'].mean().reset_index()
            fig = px.area(
                monthly_avg,
                x='Month',
                y='Total_Incentive_Received',
                title="Average Incentive per Transaction",
                labels={
                    'Month': 'Month',
                    'Total_Incentive_Received': 'Avg Incentive (₹)'
                },
                color_discrete_sequence=['#17becf']
            )
            st.plotly_chart(fig, use_container_width=True)

    def _distributor_insights_charts(self):
        """Comprehensive distributor performance analysis."""
        if self.pivot_data is not None:
            col1, col2 = st.columns(2)

            with col1:
                # Distributor-wise incentive recovery
                fig = px.bar(
                    self.pivot_data,
                    x='Distributor',
                    y='Total_Incentive_Received',
                    title="Incentive Recovery by Distributor",
                    labels={
                        'Distributor': 'Distributor',
                        'Total_Incentive_Received': 'Total Incentives (₹)'
                    },
                    color='Total_Incentive_Received',
                    color_continuous_scale='Viridis'
                )
                fig.update_xaxes(tickangle=45)
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                # Distributor margin analysis
                fig = px.scatter(
                    self.pivot_data,
                    x='Total_Incentive_Received',
                    y='Margin_Percentage',
                    size='NLC',
                    title="Distributor Performance Matrix",
                    labels={
                        'Total_Incentive_Received': 'Total Incentives (₹)',
                        'Margin_Percentage': 'Margin %',
                        'NLC': 'Net Landing Cost (₹)'
                    },
                    color='Distributor',
                    hover_name='Distributor'
                )
                st.plotly_chart(fig, use_container_width=True)

            # Top models by incentive
            model_incentives = self.pivot_data.groupby('Master_Model')['Total_Incentive_Received'].sum().nlargest(10).reset_index()
            fig = px.bar(
                model_incentives,
                x='Master_Model',
                y='Total_Incentive_Received',
                title="Top 10 Models by Incentive Value",
                labels={
                    'Master_Model': 'Device Model',
                    'Total_Incentive_Received': 'Total Incentives (₹)'
                },
                color_discrete_sequence=['#e377c2']
            )
            fig.update_xaxes(tickangle=45)
            st.plotly_chart(fig, use_container_width=True)

    def _data_quality_charts(self):
        """Data quality and validation insights."""
        # Processing status breakdown
        status_counts = self.processed_data['Processing_Status'].value_counts().reset_index()
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
                    self.processed_data['Matched_Price'].notna().sum(),
                    self.processed_data['Matched_Price'].isna().sum()
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
            'Field': ['IMEI', 'Master_Model', 'Sell_Out_Date', 'Matched_Price', 'Distributor'],
            'Completeness': [
                self.processed_data['IMEI'].notna().mean() * 100,
                self.processed_data['Master_Model'].notna().mean() * 100,
                self.processed_data['Sell_Out_Date'].notna().mean() * 100,
                self.processed_data['Matched_Price'].notna().mean() * 100,
                self.processed_data['Distributor'].notna().mean() * 100,
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

            # Column selector
            all_columns = self.processed_data.columns.tolist()
            default_cols = ['IMEI', 'Master_Model', 'Distributor', 'Matched_Price', 'Drop_Amount',
                          'Total_Incentive_Received', 'NLC', 'Margin', 'Processing_Status']

            selected_cols = st.multiselect(
                "Select columns to display:",
                all_columns,
                default=[col for col in default_cols if col in all_columns],
                key="processed_data_cols"
            )

            if selected_cols:
                display_df = st.session_state.processed_data[selected_cols].copy()

                # Format numeric columns
                numeric_cols = display_df.select_dtypes(include=[np.number]).columns
                for col in numeric_cols:
                    if col in ['Matched_Price', 'Drop_Amount', 'Total_Incentive_Received', 'NLC', 'Margin']:
                        display_df[col] = display_df[col].apply(lambda x: f"₹{x:,.0f}" if pd.notna(x) else "N/A")

                st.dataframe(display_df, use_container_width=True, hide_index=True)

                st.info(f"Showing {len(display_df)} of {len(st.session_state.processed_data)} total records")

        with tab2:
            st.subheader("Distributor Performance Summary")
            st.markdown("*Aggregated metrics by distributor*")

            if st.session_state.pivot_data is not None:
                # Format the pivot data
                display_pivot = self.pivot_data.copy()
                numeric_cols = ['Total_Incentive_Received', 'NLC', 'Final_Price', 'Margin', 'Drop_Amount']
                for col in numeric_cols:
                    if col in display_pivot.columns:
                        display_pivot[col] = display_pivot[col].apply(lambda x: f"₹{x:,.0f}")

                percentage_cols = ['Incentive_Percentage', 'Margin_Percentage']
                for col in percentage_cols:
                    if col in display_pivot.columns:
                        display_pivot[col] = display_pivot[col].apply(lambda x: f"{x:.1f}%")

                st.dataframe(display_pivot, use_container_width=True, hide_index=True)

                # Summary statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Distributors", len(display_pivot['Distributor'].unique()))
                with col2:
                    # Remove currency formatting and find max
                    incentive_values = display_pivot['Total_Incentive_Received'].str.replace('₹', '').str.replace(',', '').astype(float)
                    top_distributor = display_pivot.loc[incentive_values.idxmax(), 'Distributor']
                    st.metric("Top Performer", top_distributor)
                with col3:
                    avg_incentive_pct = display_pivot['Incentive_Percentage'].str.rstrip('%').astype(float).mean()
                    st.metric("Avg Incentive Rate", f"{avg_incentive_pct:.1f}%")

        with tab3:
            st.subheader("Model Performance Analysis")
            st.markdown("*Performance metrics by device model*")

            if st.session_state.pivot_data is not None:
                model_summary = self.pivot_data.groupby('Master_Model').agg({
                    'Total_Incentive_Received': 'sum',
                    'NLC': 'sum',
                    'Final_Price': 'sum',
                    'Margin': 'sum',
                    'Incentive_Percentage': 'mean',
                    'Margin_Percentage': 'mean'
                }).reset_index()

                # Sort by total incentives
                model_summary = model_summary.sort_values('Total_Incentive_Received', ascending=False)

                # Format for display
                display_model = model_summary.copy()
                for col in ['Total_Incentive_Received', 'NLC', 'Final_Price', 'Margin']:
                    display_model[col] = display_model[col].apply(lambda x: f"₹{x:,.0f}")

                for col in ['Incentive_Percentage', 'Margin_Percentage']:
                    display_model[col] = display_model[col].apply(lambda x: f"{x:.1f}%")

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
            success_count = len(self.processed_data[self.processed_data['Processing_Status'] == 'Completed'])
            st.metric("Successful", success_count)

        with col4:
            total_processed = len(self.processed_data)
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
            error_summary = pd.DataFrame({
                'Category': ['Processing Errors', 'Validation Warnings', 'Successful Records'],
                'Count': [
                    len([e for e in processing_errors if 'warning' not in e.lower()]),
                    len([e for e in validation_errors if 'warning' in e.lower()]),
                    len(self.processed_data[self.processed_data['Processing_Status'] == 'Completed'])
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
            self.processed_data['Matched_Price'].notna().mean() +
            self.processed_data['Master_Model'].notna().mean() +
            (self.processed_data['Processing_Status'] == 'Completed').mean()
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