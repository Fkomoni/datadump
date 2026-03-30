# Datadump - Health Insurance Analytics

## About
Health insurance data for 4 clients managed by Leadway Health HMO (Nigeria). Data includes claims, premiums, benefits, and hospital provider networks.

## Clients
- **Baker Hughes** - Plans: PROMAX. Claims: 2024 & 2025
- **Guinness** - Plans: MAX. Claims available
- **PENCOM** - Plans: PRO, PROMAX/PROFAM. Claims available
- **Leadway** - Hospital list (Lagos PHCCs) and benefit tiers (STRAWBERRY/CRANBERRY/BLUEBERRY/BLACKBERRY/RASPBERRY)

## File Structure

### Fast-loading CSVs (use these, NOT the xlsx files)
All data is pre-converted to CSV in `csv_data/`. Always load from there:
```python
import pandas as pd
df = pd.read_csv('csv_data/Baker hughes claims 2024.csv')
```

### Data Schemas

**Claims files** (~35 cols): `Claim NUmber, First Name, Surname, Member Ship No, SCHEME, SERVICE, DEPARTMENT, Provider, Treatment Date, Amt Claimed, Amt Paid, Claim Status, Diagnosis Description, Rejection Reason`

**Premium/Enrollment files** (~12 cols): `Member Enrollee ID, Member Customer Name, Member Plan, Member Date Of Birth, Member Relationship, Member Gender, Member Country State, Member Effectivedate, Client Expiry Date, Individual Premium Fees`

**Hospital lists** (9 cols): `CODE, ZONE, STATE, TOWN, PROVIDER, ADDRESS, CAT, PLAN, SPECIALTY`

**Benefit files** (2-6 cols): Service descriptions mapped to plan coverage limits

## Row Counts
| File | Rows |
|------|------|
| Baker Hughes Claims 2024 | 42,374 |
| Baker Hughes Claims 2025 | 31,275 |
| Guinness Claims | 37,079 |
| PENCOM Claims | 28,327 |
| Baker Hughes Premium 2024 | 1,901 |
| Baker Hughes Premium 2025 | 1,664 |
| Guinness Production | 2,806 |
| PENCOM Premium | 1,504 |
| Hospital Lists | ~2,600 each |

## Quick Report Generation
Run `python3 generate_report.py` to produce a full analytics summary across all clients. Use `python3 generate_report.py --client "Baker Hughes"` for a single client.

## Currency
All monetary values are in Nigerian Naira (NGN).
