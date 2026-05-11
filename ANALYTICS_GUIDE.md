# SIAT Advanced Analytics Guide

## Overview
The Advanced Analytics section provides 5 comprehensive tabs for analyzing sales, incentives, margins, trends, and data quality. This guide explains each visualization and how to interpret the insights.

---

## 📊 Tab 1: Incentive Analysis

### 1. **Incentive Distribution (Histogram)**
**What it shows:** Distribution of total incentives across all transactions

**How to analyze:**
- **Peak position**: Where most incentives cluster (e.g., ₹500-1000 range)
- **Spread**: Wide spread = varied incentive amounts; Narrow = consistent incentives
- **Outliers**: Bars far right = high-value incentive transactions
- **Shape**: 
  - Right-skewed = Most transactions have low incentives, few have high
  - Normal distribution = Balanced incentive structure

**Business insights:**
- Identify if incentives are concentrated in specific ranges
- Spot unusual high-value payouts that need review
- Understand typical incentive amounts per transaction

---

### 2. **Incentive Type Breakdown (Pie Chart)**
**What it shows:** Proportion of Percentage vs Flat incentives

**How to analyze:**
- **Percentage slice**: Shows % of total incentives from percentage schemes (e.g., 2.5% of pre-GST price)
- **Flat slice**: Shows % of total incentives from flat payouts (e.g., ₹1000 per device)

**Business insights:**
- Which incentive type dominates your scheme structure
- If flat incentives are too high, consider adjusting scheme design
- Balance between performance-based (%) and fixed (flat) incentives

---

### 3. **Incentive vs Device Price (Scatter Plot with Trendline)**
**What it shows:** Relationship between device price and incentive amount

**How to analyze:**
- **Trendline slope**: 
  - Upward = Higher-priced devices get more incentives (expected)
  - Flat = Incentives not correlated with price (potential issue)
- **Scatter pattern**:
  - Tight clustering = Consistent incentive structure
  - Wide scatter = Inconsistent or varied schemes
- **Outliers**: Points far from trendline = unusual incentive amounts

**Business insights:**
- Verify incentives scale appropriately with device value
- Identify devices with disproportionate incentives
- Ensure premium devices aren't under-incentivized

---

## 📉 Tab 2: Margin Analysis

### 1. **Price vs Net Landing Cost (Scatter Plot)**
**What it shows:** Relationship between MOP and NLC, colored by drop amount

**How to analyze:**
- **Color gradient**: 
  - Green = No drops (clean transactions)
  - Red = High drops (problematic devices)
- **Gap between points and diagonal**: Larger gap = Higher margin
- **Trendline**: Should be below 45° line (NLC < Price for profit)

**Business insights:**
- Identify which price ranges have best margins
- Spot devices with drops eating into margins (red points)
- Ensure NLC stays below purchase price for profitability

---

### 2. **Margin Distribution (Histogram)**
**What it shows:** Distribution of margins (Final Price - NLC)

**How to analyze:**
- **Positive values**: Profitable transactions (margin earned)
- **Negative values**: Loss-making transactions (NLC > Final Price)
- **Peak position**: Most common margin amount
- **Spread**: Consistency of margins across transactions

**Business insights:**
- Percentage of profitable vs loss-making transactions
- Typical margin per device
- Identify margin erosion issues

---

### 3. **Margin Percentage by Model (Bar Chart)**
**What it shows:** Margin % for each device model

**How to analyze:**
- **Tall bars**: High-margin models (good profitability)
- **Short bars**: Low-margin models (review pricing/incentives)
- **Negative bars**: Loss-making models (immediate action needed)

**Business insights:**
- Which models are most/least profitable
- Models needing scheme adjustments
- Portfolio optimization opportunities

---

## 📈 Tab 3: Performance Trends

### 1. **Monthly Incentive Trends (Line Chart)**
**What it shows:** Total incentives paid per month over time

**How to analyze:**
- **Upward trend**: Increasing incentive payouts (growing business or scheme changes)
- **Downward trend**: Decreasing payouts (reduced sales or tighter schemes)
- **Spikes**: Unusual months with high payouts (investigate causes)
- **Seasonality**: Recurring patterns (e.g., festival months)

**Business insights:**
- Track incentive budget consumption
- Identify months with unusual payout patterns
- Forecast future incentive liabilities

---

### 2. **Monthly Transaction Volume (Bar Chart)**
**What it shows:** Number of transactions per month

**How to analyze:**
- **Tall bars**: High-volume months (peak sales periods)
- **Short bars**: Low-volume months (slow periods)
- **Trend**: Growing/declining sales volume

**Business insights:**
- Sales seasonality patterns
- Correlate with incentive trends (high volume = high payouts?)
- Plan inventory and schemes for peak months

---

### 3. **Average Incentive per Transaction (Area Chart)**
**What it shows:** Average incentive amount per device over time

**How to analyze:**
- **Rising trend**: Incentives per device increasing (scheme generosity or product mix shift)
- **Falling trend**: Lower incentives per device (tighter schemes or cheaper devices)
- **Stability**: Consistent average = stable scheme structure

**Business insights:**
- Incentive efficiency (are you paying more per device?)
- Impact of scheme changes on average payouts
- Product mix effects (premium vs budget devices)

---

## 🏢 Tab 4: Distributor Insights

### 1. **Incentive Recovery by Distributor (Bar Chart)**
**What it shows:** Total incentives owed to each distributor

**How to analyze:**
- **Tallest bars**: Distributors with highest incentive claims
- **Color intensity**: Darker = Higher amounts
- **Comparison**: Relative performance across distributors

**Business insights:**
- Which distributors drive most sales volume
- Incentive liability per distributor
- Identify top-performing partners

---

### 2. **Distributor Performance Matrix (Bubble Chart)**
**What it shows:** Incentives vs Margin, bubble size = NLC

**How to analyze:**
- **X-axis (Incentives)**: Higher = More sales volume
- **Y-axis (Margin)**: Higher = Better profitability
- **Bubble size**: Larger = Higher total business value
- **Top-right quadrant**: Best distributors (high volume + high margin)
- **Bottom-right**: High volume but low margin (review pricing)
- **Top-left**: Low volume but high margin (growth opportunity)

**Business insights:**
- Identify star performers (top-right)
- Distributors needing support (bottom-left)
- Balance volume vs profitability

---

### 3. **Top 10 Models by Incentive Value (Bar Chart)**
**What it shows:** Models with highest total incentive payouts

**How to analyze:**
- **Ranking**: Which models cost most in incentives
- **Gap between bars**: Concentration of incentives

**Business insights:**
- Models driving incentive costs
- Focus areas for scheme optimization
- Popular models in your portfolio

---

## 🔍 Tab 5: Data Quality

### 1. **Data Processing Status (Pie Chart)**
**What it shows:** Breakdown of record completeness

**How to analyze:**
- **Complete (Green)**: Fully processed records
- **Price Missing (Red)**: Records without MOP match
- **Incomplete (Orange)**: Missing critical fields

**Business insights:**
- Data quality percentage
- Issues preventing full processing
- Areas needing data cleanup

---

### 2. **Price Matching Success Rate (Pie Chart)**
**What it shows:** % of records with successful price lookups

**How to analyze:**
- **Price Matched (Blue)**: Successfully matched to price list
- **Price Missing (Red)**: Failed to match (model not in price list or date issues)

**Business insights:**
- Price list coverage
- Models missing from price master
- Date validation issues

---

### 3. **Data Completeness Radar (Radar Chart)**
**What it shows:** Completeness % for each critical field

**How to analyze:**
- **Shape**: 
  - Perfect circle (100% all around) = Excellent data quality
  - Irregular shape = Some fields have missing data
- **Dips**: Fields with lower completeness (need attention)

**Business insights:**
- Overall data quality score
- Specific fields needing improvement
- Data entry process issues

---

## 🎯 How to Use Analytics for Decision Making

### For Finance Teams:
1. **Incentive Analysis** → Budget planning and payout forecasting
2. **Margin Analysis** → Profitability tracking and pricing decisions
3. **Performance Trends** → Monthly accruals and liability management

### For Sales Teams:
1. **Distributor Insights** → Partner performance evaluation
2. **Performance Trends** → Sales volume tracking
3. **Top Models** → Focus on high-performing products

### For Operations Teams:
1. **Data Quality** → Process improvement areas
2. **Price Matching** → Master data maintenance
3. **Completeness Radar** → Data entry training needs

### For Management:
1. **Executive Summary** → Overall business health
2. **Distributor Performance Matrix** → Strategic partner decisions
3. **Margin Analysis** → Profitability optimization

---

## 💡 Pro Tips

1. **Compare periods**: Use date filters to compare month-over-month or year-over-year
2. **Drill down**: Click on charts to filter and explore specific segments
3. **Export insights**: Download charts as images for presentations
4. **Regular monitoring**: Review analytics weekly to catch issues early
5. **Correlate metrics**: Look at multiple tabs together for complete picture

---

## 🚨 Red Flags to Watch For

- **Incentive Distribution**: Sudden spikes or unusual patterns
- **Margin Analysis**: Increasing negative margins
- **Performance Trends**: Declining average incentive (may indicate data issues)
- **Distributor Matrix**: Distributors in bottom-left quadrant (low volume + low margin)
- **Data Quality**: Completeness below 90%

---

## 📞 Support

For questions about interpreting analytics or customizing visualizations, refer to the main README.md or contact the development team.
