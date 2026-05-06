# Sales & Incentive Automation Tool (SIAT)

A Python-based ETL application that automates the reconciliation of mobile phone sales data by calculating price protections, promotional schemes, and Net Landing Costs (NLC).

## Features

### Core Functionality
- **11-Step Calculation Engine**: Implements precise business logic for incentive calculations
- **Multi-Source Data Integration**: Handles Excel/CSV files with various structures and encodings
- **Professional Dashboard**: Web-based UI with interactive visualizations using Streamlit and Plotly
- **Data Integrity**: Built-in validation for duplicates, fuzzy matching, and date consistency

### Key Calculations
1. **Drop Detection**: Match IMEIs against drop dump
2. **Price Matching**: Lookup purchase prices with date validation
3. **Tax Calculations**: GST adjustments (18% rate)
4. **Scheme Application**: Percentage and flat payout incentives
5. **NLC Calculation**: Net Landing Cost computation
6. **Pivot Reporting**: Distributor-wise summaries

## Requirements

- Python 3.8+
- Dependencies listed in `requirements.txt`

## Installation

1. Clone or download the project
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Dashboard Mode (Recommended)
```bash
python main.py
```
This launches the Streamlit web dashboard where you can upload files and view results interactively.

### Command Line Mode
```bash
python main.py --cli
```
Batch processing interface (under development).

### Testing
```bash
python main.py --test
```
Run basic validation tests.

## Data File Formats

### Required Input Files

1. **Drop Dump** (Excel/CSV, no headers)
   - Column 0: IMEI numbers that incurred drops

2. **Price List** (Excel/CSV, headers on row 2)
   - Master_Model: Product model identifier
   - Purchase_Price: Base purchase price
   - Valid_From/Valid_To: Price validity dates

3. **Scheme File** (Excel/CSV, headers on row 2)
   - Master_Model: Product model
   - Scheme_Type: "Percentage" or "Flat"
   - Scheme_Value: Incentive amount/percentage
   - Scheme_Start_Date/Scheme_End_Date: Validity period

4. **Sales Data** (Excel/CSV, headers on row 2)
   - IMEI: Device identifier
   - Master_Model: Product model
   - Sell_Out_Date: Sale date
   - Purchase_Price: Transaction price
   - Distributor: Distributor name

## Dashboard Features

### Visualizations
- **Total Incentive Recovery**: Overall owed amounts by distributor
- **Margin Analysis**: Purchase price vs NLC scatter plots
- **Payout Trends**: Monthly incentive growth/decline
- **Error Logs**: Visual alerts for data issues

### Data Tables
- Processed transaction details
- Distributor-wise summaries
- Validation error logs

## Technical Architecture

```
src/
├── data/           # Data loading and ingestion
├── calculations/   # Core calculation engine
├── ui/            # Dashboard and user interface
└── utils/         # Helper utilities
```

## Business Logic

### 11-Step Process
1. Match IMEI against drop dump → populate Drop column
2. Lookup Master_Model in Price List → validate dates
3. Calculate Final Price = Purchase Price - Drop
4. Pre-GST Price = Final Price / 1.18
5. Match schemes by model and date
6. Apply percentage/flat incentives to Pre-GST price
7. Sum all incentives → Total_Incentive_Received
8. NLC = Final Price - Total_Incentive_Received
9. Generate distributor pivot reports

## Data Validation

- **Duplicate Prevention**: No multiple payouts per IMEI
- **Fuzzy Matching**: Handle model name variations (80% similarity threshold)
- **Date Validation**: Flag sales before purchase dates
- **Encoding Support**: Latin-1 and UTF-8 handling

## Deployment

The application is designed for portability:
- One-click executable generation possible
- Responsive design for desktop/tablet
- Scalable to thousands of records

## Contributing

1. Follow the existing code structure
2. Add tests for new features
3. Update documentation
4. Ensure compatibility with requirements.txt

## License

This project implements the specific business logic outlined in the SRS document.