#!/usr/bin/env python3
"""
Tally Data Export Connector
Exports all Tally data in XML format using ODBC on port 9000.
Creates separate XML files for each data type.
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
        Export all data from the selected company to separate XML files.
        
        Args:
            company_name: Name of the company to export
            output_folder: Base folder where export folders will be created
            
        Returns:
            tuple: (export_folder_path, summary_dict)
        """
        # Create output folder if it doesn't exist
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
            print(f"✓ Created output folder: {output_folder}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_company_name = "".join(c for c in company_name if c.isalnum() or c in (' ', '-', '_')).strip()
        export_folder = os.path.join(output_folder, f"{safe_company_name}_{timestamp}")
        
        # Create company-specific export folder
        os.makedirs(export_folder)
        print(f"✓ Created export folder: {export_folder}")

        # Summary dictionary to track export statistics
        summary = {
            "company_name": company_name,
            "export_time": datetime.now().isoformat(),
            "export_folder": export_folder,
            "files": {}
        }

        # Export each master type to separate XML file
        files_to_export = [
            ("Ledgers.xml", self._export_ledgers),
            ("Groups.xml", self._export_groups),
            ("VoucherTypes.xml", self._export_voucher_types),
            ("CostCenters.xml", self._export_cost_centers),
            ("StockGroups.xml", self._export_stock_groups),
            ("StockItems.xml", self._export_stock_items),
            ("Units.xml", self._export_units),
            ("Currencies.xml", self._export_currencies),
            ("Vouchers.xml", self._export_vouchers),
        ]

        for filename, export_func in files_to_export:
            filepath = os.path.join(export_folder, filename)
            count = export_func(filepath)
            summary["files"][filename] = count
            if count > 0:
                print(f"✓ Exported {count} records to {filename}")

        # Create export summary file
        summary_path = os.path.join(export_folder, "export_summary.txt")
        self._create_summary_file(summary_path, summary)
        summary["files"]["export_summary.txt"] = "N/A"
        print(f"✓ Created export_summary.txt")

        return export_folder, summary

    def _create_xml_root(self, entity_type, company_name):
        """Create a standard XML root element."""
        root = ET.Element(entity_type.upper())
        root.set("version", "1.0")
        root.set("generated", datetime.now().isoformat())
        root.set("company", company_name)
        return root

    def _write_xml_file(self, root, filepath):
        """Write XML to file with proper formatting."""
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(filepath, encoding="utf-8", xml_declaration=True)
        return filepath

    def _export_ledgers(self, filepath):
        """Export ledgers to separate XML file."""
        root = self._create_xml_root("LEDGERS", "N/A")
        try:
            self.cursor.execute("""
                SELECT $Name, $Parent, $OpeningBalance, $IsBillWiseOn
                FROM Ledger
            """)
            rows = self.cursor.fetchall()
            columns = [desc[0] for desc in self.cursor.description]
            
            for row in rows:
                ledger_elem = ET.SubElement(root, "LEDGER")
                for col_name, value in zip(columns, row):
                    if value is not None:
                        field_elem = ET.SubElement(ledger_elem, col_name.replace("$", ""))
                        field_elem.text = str(value)
            
            self._write_xml_file(root, filepath)
            return len(rows)
        except pyodbc.Error:
            self._write_xml_file(root, filepath)
            return 0

    def _export_groups(self, filepath):
        """Export groups to separate XML file."""
        root = self._create_xml_root("GROUPS", "N/A")
        try:
            self.cursor.execute("""
                SELECT $Name, $Parent, $NatureOfGroup
                FROM Groups
            """)
            rows = self.cursor.fetchall()
            columns = [desc[0] for desc in self.cursor.description]
            
            for row in rows:
                group_elem = ET.SubElement(root, "GROUP")
                for col_name, value in zip(columns, row):
                    if value is not None:
                        field_elem = ET.SubElement(group_elem, col_name.replace("$", ""))
                        field_elem.text = str(value)
            
            self._write_xml_file(root, filepath)
            return len(rows)
        except pyodbc.Error:
            self._write_xml_file(root, filepath)
            return 0

    def _export_voucher_types(self, filepath):
        """Export voucher types to separate XML file."""
        root = self._create_xml_root("VOUCHER_TYPES", "N/A")
        try:
            self.cursor.execute("""
                SELECT $Name, $Parent, $Abbreviation, $NumberingMethod
                FROM VoucherType
            """)
            rows = self.cursor.fetchall()
            columns = [desc[0] for desc in self.cursor.description]
            
            for row in rows:
                vtype_elem = ET.SubElement(root, "VOUCHER_TYPE")
                for col_name, value in zip(columns, row):
                    if value is not None:
                        field_elem = ET.SubElement(vtype_elem, col_name.replace("$", ""))
                        field_elem.text = str(value)
            
            self._write_xml_file(root, filepath)
            return len(rows)
        except pyodbc.Error:
            self._write_xml_file(root, filepath)
            return 0

    def _export_cost_centers(self, filepath):
        """Export cost centers to separate XML file."""
        root = self._create_xml_root("COST_CENTERS", "N/A")
        try:
            self.cursor.execute("""
                SELECT $Name, $Parent, $IsRevenue
                FROM CostCenter
            """)
            rows = self.cursor.fetchall()
            columns = [desc[0] for desc in self.cursor.description]
            
            for row in rows:
                cc_elem = ET.SubElement(root, "COST_CENTER")
                for col_name, value in zip(columns, row):
                    if value is not None:
                        field_elem = ET.SubElement(cc_elem, col_name.replace("$", ""))
                        field_elem.text = str(value)
            
            self._write_xml_file(root, filepath)
            return len(rows)
        except pyodbc.Error:
            self._write_xml_file(root, filepath)
            return 0

    def _export_stock_groups(self, filepath):
        """Export stock groups to separate XML file."""
        root = self._create_xml_root("STOCK_GROUPS", "N/A")
        try:
            self.cursor.execute("""
                SELECT $Name, $Parent
                FROM StockGroup
            """)
            rows = self.cursor.fetchall()
            columns = [desc[0] for desc in self.cursor.description]
            
            for row in rows:
                sg_elem = ET.SubElement(root, "STOCK_GROUP")
                for col_name, value in zip(columns, row):
                    if value is not None:
                        field_elem = ET.SubElement(sg_elem, col_name.replace("$", ""))
                        field_elem.text = str(value)
            
            self._write_xml_file(root, filepath)
            return len(rows)
        except pyodbc.Error:
            self._write_xml_file(root, filepath)
            return 0

    def _export_stock_items(self, filepath):
        """Export stock items to separate XML file."""
        root = self._create_xml_root("STOCK_ITEMS", "N/A")
        try:
            self.cursor.execute("""
                SELECT $Name, $Parent, $BaseUnits, $OpeningBalance, 
                       $ClosingBalance, $StandardCost, $StandardPrice
                FROM StockItem
            """)
            rows = self.cursor.fetchall()
            columns = [desc[0] for desc in self.cursor.description]
            
            for row in rows:
                item_elem = ET.SubElement(root, "STOCK_ITEM")
                for col_name, value in zip(columns, row):
                    if value is not None:
                        field_elem = ET.SubElement(item_elem, col_name.replace("$", ""))
                        field_elem.text = str(value)
            
            self._write_xml_file(root, filepath)
            return len(rows)
        except pyodbc.Error:
            self._write_xml_file(root, filepath)
            return 0

    def _export_units(self, filepath):
        """Export units to separate XML file."""
        root = self._create_xml_root("UNITS", "N/A")
        try:
            self.cursor.execute("""
                SELECT $Name, $BaseUnits, $Symbol
                FROM Unit
            """)
            rows = self.cursor.fetchall()
            columns = [desc[0] for desc in self.cursor.description]
            
            for row in rows:
                unit_elem = ET.SubElement(root, "UNIT")
                for col_name, value in zip(columns, row):
                    if value is not None:
                        field_elem = ET.SubElement(unit_elem, col_name.replace("$", ""))
                        field_elem.text = str(value)
            
            self._write_xml_file(root, filepath)
            return len(rows)
        except pyodbc.Error:
            self._write_xml_file(root, filepath)
            return 0

    def _export_currencies(self, filepath):
        """Export currencies to separate XML file."""
        root = self._create_xml_root("CURRENCIES", "N/A")
        try:
            self.cursor.execute("""
                SELECT $Name, $Symbol, $IsBaseCurrency
                FROM Currency
            """)
            rows = self.cursor.fetchall()
            columns = [desc[0] for desc in self.cursor.description]
            
            for row in rows:
                curr_elem = ET.SubElement(root, "CURRENCY")
                for col_name, value in zip(columns, row):
                    if value is not None:
                        field_elem = ET.SubElement(curr_elem, col_name.replace("$", ""))
                        field_elem.text = str(value)
            
            self._write_xml_file(root, filepath)
            return len(rows)
        except pyodbc.Error:
            self._write_xml_file(root, filepath)
            return 0

    def _export_vouchers(self, filepath):
        """Export vouchers to separate XML file."""
        root = self._create_xml_root("VOUCHERS", "N/A")
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
                voucher_elem = ET.SubElement(root, "VOUCHER")
                for col_name, value in zip(columns, row):
                    if value is not None:
                        field_elem = ET.SubElement(voucher_elem, col_name.replace("$", ""))
                        field_elem.text = str(value)

                # Try to get voucher ledger entries
                try:
                    date_val = str(row[0])
                    vtype = str(row[1]) if row[1] else ""
                    vnum = str(row[2]) if row[2] else ""
                    
                    if vtype and vnum:
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

            self._write_xml_file(root, filepath)
            return len(rows)
        except pyodbc.Error:
            self._write_xml_file(root, filepath)
            return 0

    def _create_summary_file(self, filepath, summary):
        """Create export summary text file."""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("TALLY DATA EXPORT SUMMARY\n")
            f.write("=" * 60 + "\n\n")
            
            f.write(f"Company Name: {summary['company_name']}\n")
            f.write(f"Export Time: {summary['export_time']}\n")
            f.write(f"Export Folder: {summary['export_folder']}\n\n")
            
            f.write("=" * 60 + "\n")
            f.write("EXPORTED FILES\n")
            f.write("=" * 60 + "\n\n")
            
            total_records = 0
            for filename, count in summary['files'].items():
                if filename != "export_summary.txt":
                    f.write(f"• {filename:<25} : {count} records\n")
                    if isinstance(count, int):
                        total_records += count
                else:
                    f.write(f"• {filename:<25} : Summary file\n")
            
            f.write("\n" + "=" * 60 + "\n")
            f.write(f"TOTAL RECORDS: {total_records}\n")
            f.write("=" * 60 + "\n")


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
        export_folder, summary = connector.export_company_data(selected_company_name)

        print("\n" + "=" * 50)
        print("EXPORT COMPLETE!")
        print("=" * 50)
        print(f"Export Folder: {export_folder}")
        print(f"\nFiles created:")
        for filename, count in summary['files'].items():
            if filename != "export_summary.txt":
                print(f"  • {filename} ({count} records)")
            else:
                print(f"  • {filename}")
        print("=" * 50)

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
    except Exception as e:
        print(f"\n✗ Error: {e}")
    finally:
        connector.disconnect()


if __name__ == "__main__":
    main()
