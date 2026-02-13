#!/usr/bin/env python3
"""
Tally Data Export Connector
Exports all Tally data in XML format using ODBC on port 9000.
"""

import pyodbc
import xml.etree.ElementTree as ET
import os
from datetime import datetime


class TallyODBCConnector:
    """Connects to Tally via ODBC and exports data to XML."""

    def __init__(self, host="localhost", port=9000):
        self.host = host
        self.port = port
        self.connection_string = (
            f"DRIVER={{Tally ODBC Driver}};"
            f"SERVER={host};"
            f"PORT={port};"
        )
        self.conn = None
        self.cursor = None

    def connect(self):
        """Establish connection to Tally via ODBC."""
        try:
            self.conn = pyodbc.connect(self.connection_string)
            self.cursor = self.conn.cursor()
            print(f"✓ Connected to Tally at {self.host}:{self.port}")
            return True
        except pyodbc.Error as e:
            print(f"✗ Failed to connect to Tally: {e}")
            return False

    def disconnect(self):
        """Close the ODBC connection."""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            print("✓ Disconnected from Tally")

    def get_companies(self):
        """
        Fetch all available companies from Tally.
        Works regardless of whether company is on local/network drive.
        Tally stores company names independently of their data path location.
        Returns list of tuples: (company_name, data_path)
        """
        companies = []
        try:
            # Query to get company names and paths from Tally
            # This works for companies stored locally, on network drives,
            # external drives, or any accessible location
            try:
                self.cursor.execute("SELECT $Name, $DataPath FROM Company")
                rows = self.cursor.fetchall()
                for row in rows:
                    if row[0]:
                        company_name = str(row[0]).strip()
                        data_path = str(row[1]).strip() if row[1] else "N/A"
                        if company_name:
                            companies.append((company_name, data_path))
            except pyodbc.Error:
                # Fallback to just getting names if DataPath is not available
                self.cursor.execute("SELECT $Name FROM Company")
                rows = self.cursor.fetchall()
                for row in rows:
                    if row[0]:
                        company_name = str(row[0]).strip()
                        if company_name:
                            companies.append((company_name, "N/A"))

            # Also try alternate query if first one returns empty
            if not companies:
                try:
                    self.cursor.execute("SELECT $Name FROM CompanyCollection")
                    rows = self.cursor.fetchall()
                    for row in rows:
                        if row[0]:
                            company_name = str(row[0]).strip()
                            if company_name:
                                companies.append((company_name, "N/A"))
                except pyodbc.Error:
                    pass

        except pyodbc.Error as e:
            print(f"Error fetching companies: {e}")
        return companies

    def export_company_data(self, company_name, output_folder="tally_exports"):
        """
        Export all data from the selected company to XML.
        
        Args:
            company_name: Name of the company to export
            output_folder: Folder where XML files will be saved
        """
        # Create output folder if it doesn't exist
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
            print(f"✓ Created output folder: {output_folder}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_company_name = "".join(c for c in company_name if c.isalnum() or c in (' ', '-', '_')).strip()
        filename = f"{safe_company_name}_{timestamp}.xml"
        filepath = os.path.join(output_folder, filename)

        # Create XML structure
        root = ET.Element("TALLYEXPORT")
        root.set("version", "1.0")
        root.set("generated", datetime.now().isoformat())
        root.set("company", company_name)

        company_elem = ET.SubElement(root, "COMPANY")
        company_elem.set("name", company_name)

        # Export Masters (Ledgers, Groups, Stock Items, etc.)
        masters_elem = ET.SubElement(company_elem, "MASTERS")
        self._export_masters(masters_elem)

        # Export Vouchers (Transactions)
        vouchers_elem = ET.SubElement(company_elem, "VOUCHERS")
        self._export_vouchers(vouchers_elem)

        # Export Stock Data
        stock_elem = ET.SubElement(company_elem, "STOCK")
        self._export_stock(stock_elem)

        # Export Balance Sheet Data
        balances_elem = ET.SubElement(company_elem, "BALANCES")
        self._export_balances(balances_elem)

        # Write to file
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(filepath, encoding="utf-8", xml_declaration=True)

        print(f"✓ Data exported to: {filepath}")
        return filepath

    def _export_masters(self, parent_elem):
        """Export master data (Ledgers, Groups, Cost Centers, etc.)."""
        masters_data = {
            "LEDGERS": "SELECT $Name, $Parent, $OpeningBalance FROM Ledger",
            "GROUPS": "SELECT $Name, $Parent FROM Groups",
            "COST_CENTERS": "SELECT $Name, $Parent FROM CostCenter",
            "STOCK_GROUPS": "SELECT $Name, $Parent FROM StockGroup",
            "STOCK_ITEMS": "SELECT $Name, $Parent, $BaseUnits FROM StockItem",
            "UNITS": "SELECT $Name, $BaseUnits FROM Unit",
            "CURRENCIES": "SELECT $Name, $Symbol FROM Currency",
            "VOUCHER_TYPES": "SELECT $Name, $Parent FROM VoucherType",
        }

        for master_name, query in masters_data.items():
            try:
                self.cursor.execute(query)
                rows = self.cursor.fetchall()
                if rows:
                    master_elem = ET.SubElement(parent_elem, master_name)
                    columns = [desc[0] for desc in self.cursor.description]
                    for row in rows:
                        item_elem = ET.SubElement(master_elem, "ITEM")
                        for col_name, value in zip(columns, row):
                            if value is not None:
                                field_elem = ET.SubElement(item_elem, col_name.replace("$", ""))
                                field_elem.text = str(value)
            except pyodbc.Error:
                # Some masters might not exist in all Tally versions
                pass

    def _export_vouchers(self, parent_elem):
        """Export voucher/transaction data."""
        try:
            self.cursor.execute("""
                SELECT 
                    $Date, $VoucherTypeName, $VoucherNumber, 
                    $PartyLedgerName, $Narration, $Amount
                FROM Voucher
            """)
            rows = self.cursor.fetchall()
            columns = [desc[0] for desc in self.cursor.description]

            for row in rows:
                voucher_elem = ET.SubElement(parent_elem, "VOUCHER")
                for col_name, value in zip(columns, row):
                    if value is not None:
                        field_elem = ET.SubElement(voucher_elem, col_name.replace("$", ""))
                        field_elem.text = str(value)

                # Get voucher ledger entries
                try:
                    date_val = row[0]
                    vtype = row[1]
                    vnum = row[2]
                    self.cursor.execute(f"""
                        SELECT $LedgerName, $Amount, $IsDeemedPositive 
                        FROM AccountingAllocations 
                        WHERE $VoucherDate = '{date_val}' 
                        AND $VoucherTypeName = '{vtype}' 
                        AND $VoucherNumber = '{vnum}'
                    """)
                    entries = self.cursor.fetchall()
                    entries_elem = ET.SubElement(voucher_elem, "ENTRIES")
                    for entry in entries:
                        entry_elem = ET.SubElement(entries_elem, "ENTRY")
                        ledger_elem = ET.SubElement(entry_elem, "LEDGER")
                        ledger_elem.text = str(entry[0])
                        amount_elem = ET.SubElement(entry_elem, "AMOUNT")
                        amount_elem.text = str(entry[1])
                except pyodbc.Error:
                    pass

        except pyodbc.Error as e:
            print(f"Warning: Could not export vouchers: {e}")

    def _export_stock(self, parent_elem):
        """Export stock-related data."""
        try:
            self.cursor.execute("""
                SELECT $Name, $BaseUnits, $ClosingBalance, $OpeningBalance,
                       $StockGroup, $StandardCost, $StandardPrice
                FROM StockItem
            """)
            rows = self.cursor.fetchall()
            columns = [desc[0] for desc in self.cursor.description]

            for row in rows:
                item_elem = ET.SubElement(parent_elem, "STOCK_ITEM")
                for col_name, value in zip(columns, row):
                    if value is not None:
                        field_elem = ET.SubElement(item_elem, col_name.replace("$", ""))
                        field_elem.text = str(value)
        except pyodbc.Error:
            pass

        # Stock voucher entries
        try:
            self.cursor.execute("""
                SELECT $StockItemName, $Rate, $Amount, $BilledQty, $ActualQty
                FROM InventoryEntries
            """)
            rows = self.cursor.fetchall()
            entries_elem = ET.SubElement(parent_elem, "INVENTORY_ENTRIES")
            columns = [desc[0] for desc in self.cursor.description]

            for row in rows:
                entry_elem = ET.SubElement(entries_elem, "ENTRY")
                for col_name, value in zip(columns, row):
                    if value is not None:
                        field_elem = ET.SubElement(entry_elem, col_name.replace("$", ""))
                        field_elem.text = str(value)
        except pyodbc.Error:
            pass

    def _export_balances(self, parent_elem):
        """Export balance sheet related data."""
        try:
            # Get ledger balances
            self.cursor.execute("""
                SELECT $Name, $ClosingBalance, $OpeningBalance
                FROM Ledger
            """)
            rows = self.cursor.fetchall()
            columns = [desc[0] for desc in self.cursor.description]

            for row in rows:
                balance_elem = ET.SubElement(parent_elem, "LEDGER_BALANCE")
                for col_name, value in zip(columns, row):
                    if value is not None:
                        field_elem = ET.SubElement(balance_elem, col_name.replace("$", ""))
                        field_elem.text = str(value)
        except pyodbc.Error:
            pass


def display_company_menu(companies):
    """Display company selection menu with location info."""
    print("\n" + "=" * 60)
    print("AVAILABLE COMPANIES")
    print("=" * 60)
    for idx, (company_name, data_path) in enumerate(companies, 1):
        print(f"  [{idx}] {company_name}")
        if data_path and data_path != "N/A":
            # Show truncated path if too long
            display_path = data_path if len(data_path) <= 45 else "..." + data_path[-42:]
            print(f"      Location: {display_path}")
    print("=" * 60)


def main():
    """Main function to run the Tally export process."""
    print("\n" + "=" * 50)
    print("TALLY DATA EXPORT CONNECTOR")
    print("=" * 50)
    print("Connecting to Tally via ODBC on port 9000...")

    # Initialize connector
    connector = TallyODBCConnector(host="localhost", port=9000)

    # Connect to Tally
    if not connector.connect():
        print("\nPlease ensure:")
        print("1. Tally is running")
        print("2. ODBC is enabled in Tally (F12 > Advanced Configuration)")
        print("3. Port 9000 is not blocked by firewall")
        return

    try:
        # Get list of companies
        companies = connector.get_companies()

        if not companies:
            print("\nNo companies found in Tally.")
            return

        # Display menu and let user select
        display_company_menu(companies)

        while True:
            try:
                choice = input(f"\nSelect company (1-{len(companies)}): ").strip()
                choice_num = int(choice)
                if 1 <= choice_num <= len(companies):
                    selected_company_name, selected_company_path = companies[choice_num - 1]
                    break
                else:
                    print(f"Please enter a number between 1 and {len(companies)}")
            except ValueError:
                print("Please enter a valid number")

        print(f"\n→ Selected Company: {selected_company_name}")
        if selected_company_path and selected_company_path != "N/A":
            print(f"→ Data Location: {selected_company_path}")
        print("→ Exporting data, please wait...")

        # Export data
        output_path = connector.export_company_data(selected_company_name)

        print("\n" + "=" * 50)
        print("EXPORT COMPLETE!")
        print("=" * 50)
        print(f"File: {output_path}")
        print("=" * 50)

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
    except Exception as e:
        print(f"\n✗ Error: {e}")
    finally:
        connector.disconnect()


if __name__ == "__main__":
    main()
