# Data Analytics Project — Leadway Health / Baker Hughes

## Project Context

This repository contains healthcare and insurance data for **Leadway Health Insurance (LWH)** and **Baker Hughes** employee benefits. The data includes:

- **Claims data** (2024 & 2025) — Baker Hughes employee health claims
- **Premium data** (2024 & 2025) — Baker Hughes premium records
- **Provider lists** — Hospital/provider networks (LWH standard & Baker Hughes standard)
- **Benefit plans** — LWH 2026 standard benefits, Baker Hughes benefits

## Analytics Skill Instructions

When working with this data, **always apply data analytics best practices**:

### Data Loading & Exploration
- Use Python with `pandas` and `openpyxl` for reading `.xlsx` files
- Always start by loading and inspecting the data: shape, dtypes, null counts, summary statistics
- Profile the data before any analysis (check for duplicates, missing values, outliers)

### Analysis Approach
- Provide clear, quantitative answers with supporting numbers
- Use descriptive statistics (mean, median, percentiles, distributions)
- When comparing periods (2024 vs 2025), calculate year-over-year changes
- Identify trends, anomalies, and key drivers in the data
- Cross-reference related datasets (e.g., claims vs premiums, providers vs benefits)

### Visualization
- Use `matplotlib` or `seaborn` for charts and visualizations
- Always label axes, add titles, and include legends where appropriate
- Choose chart types appropriate to the data (bar charts for categories, line charts for trends, histograms for distributions)

### Output & Reporting
- Summarize findings in clear, business-friendly language
- Highlight actionable insights (cost drivers, utilization patterns, network gaps)
- When asked to generate reports, structure them with executive summary, key findings, and detailed analysis

### File Reference
| File | Description |
|------|-------------|
| `Baker hughes claims 2024.xlsx` | Claims records for 2024 |
| `Baker hughes claims 2025.xlsx` | Claims records for 2025 |
| `Baker hughes premium 2024.xlsx` | Premium records for 2024 |
| `Baker hughes premium 2025.xlsx` | Premium records for 2025 |
| `BAKER HUGHES BENEFIT.xlsx` | Baker Hughes benefit plan |
| `Baker hughes HOSPITAL LIST (STANDARD).xlsx` | Baker Hughes provider network |
| `2025 LH Provider List standard leadway hospital list.xlsx` | LWH standard provider list |
| `2026 STANDARD BENEFIT LWH.xlsx` | LWH 2026 standard benefit plan |
