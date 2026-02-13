# Tally Data Export Connector

A Python script that exports all Tally accounting data in XML format using ODBC connection on port 9000.

## Features

- Lists all available Tally companies (works with local and network drive locations)
- Interactive company selection menu
- Exports comprehensive data including:
  - Masters (Ledgers, Groups, Cost Centers, Stock Items, Units, Currencies, Voucher Types)
  - Vouchers (Transactions with ledger entries)
  - Stock data (Stock items and inventory entries)
  - Balance sheet data (Ledger balances)
- Saves data as XML with timestamp in filename
- Works regardless of where the Tally company data is stored (local or network drive)

## Prerequisites

1. **Tally ERP 9 / Tally Prime** must be installed and running
2. **Tally ODBC Driver** must be installed on your system
3. **ODBC must be enabled** in Tally:
   - Press `F12` (Configure)
   - Go to `Advanced Configuration`
   - Enable `ODBC` and set port to `9000`

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python tally_export.py
```

### Steps:

1. Ensure Tally is running with ODBC enabled on port 9000
2. Run the script
3. Select the company from the displayed list
4. Data will be exported to `tally_exports/` folder as XML

## Output

Exported XML files are saved in the `tally_exports/` folder with the naming format:
```
<CompanyName>_YYYYMMDD_HHMMSS.xml
```

## Troubleshooting

### Connection Failed
- Ensure Tally is running
- Verify ODBC is enabled in Tally settings (port 9000)
- Check if port 9000 is blocked by firewall

### No Companies Found
- Make sure at least one company is loaded in Tally
- Check that the company data path is accessible

### ODBC Driver Not Found
- Install Tally ODBC Driver from your Tally installation

## Requirements

- Python 3.7+
- pyodbc
- Tally ODBC Driver
