#!/usr/bin/env python
"""
Google Sheets MCP Client
A simple client for interacting with the Google Sheets MCP server.
"""

import argparse
import json
import requests

class MCPClient:
    """Simple MCP client implementation"""
    
    def __init__(self, server_name):
        self.server_name = server_name
        self.base_url = f"http://localhost:8000/mcp/{server_name}"
    
    def _call_method(self, method_name, **kwargs):
        """Call an MCP method with the given arguments"""
        url = f"{self.base_url}/{method_name}"
        response = requests.post(url, json=kwargs)
        response.raise_for_status()
        return response.json()
    
    def __getattr__(self, name):
        """Dynamically create methods for the MCP server"""
        return lambda **kwargs: self._call_method(name, **kwargs)

def main():
    parser = argparse.ArgumentParser(description="Google Sheets MCP Client")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # List spreadsheets command
    list_parser = subparsers.add_parser("list", help="List available spreadsheets")
    
    # Create spreadsheet command
    create_parser = subparsers.add_parser("create", help="Create a new spreadsheet")
    create_parser.add_argument("title", help="Title for the new spreadsheet")
    
    # Get sheet data command
    get_parser = subparsers.add_parser("get", help="Get data from a spreadsheet")
    get_parser.add_argument("spreadsheet_id", help="ID of the spreadsheet")
    get_parser.add_argument("sheet", help="Name of the sheet")
    get_parser.add_argument("--range", help="Cell range in A1 notation (e.g., 'A1:C10')")
    
    # Update cells command
    update_parser = subparsers.add_parser("update", help="Update cells in a spreadsheet")
    update_parser.add_argument("spreadsheet_id", help="ID of the spreadsheet")
    update_parser.add_argument("sheet", help="Name of the sheet")
    update_parser.add_argument("range", help="Cell range in A1 notation (e.g., 'A1:C10')")
    update_parser.add_argument("data", help="JSON string of 2D array with values")
    
    # List sheets command
    sheets_parser = subparsers.add_parser("sheets", help="List all sheets in a spreadsheet")
    sheets_parser.add_argument("spreadsheet_id", help="ID of the spreadsheet")
    
    # Create sheet command
    create_sheet_parser = subparsers.add_parser("create-sheet", help="Create a new sheet in a spreadsheet")
    create_sheet_parser.add_argument("spreadsheet_id", help="ID of the spreadsheet")
    create_sheet_parser.add_argument("title", help="Title for the new sheet")
    
    args = parser.parse_args()
    
    # Connect to the MCP server
    client = MCPClient("google-sheets")
    
    if args.command == "list":
        # List all spreadsheets
        result = client.list_spreadsheets()
        print(json.dumps(result, indent=2))
        
    elif args.command == "create":
        # Create a new spreadsheet
        result = client.create_spreadsheet(title=args.title)
        print(f"Created spreadsheet: {result['title']}")
        print(f"ID: {result['spreadsheetId']}")
        print(f"Sheets: {', '.join(result['sheets'])}")
        
    elif args.command == "get":
        # Get data from a spreadsheet
        result = client.get_sheet_data(
            spreadsheet_id=args.spreadsheet_id,
            sheet=args.sheet,
            range=args.range
        )
        print(json.dumps(result, indent=2))
        
    elif args.command == "update":
        # Update cells in a spreadsheet
        data = json.loads(args.data)
        result = client.update_cells(
            spreadsheet_id=args.spreadsheet_id,
            sheet=args.sheet,
            range=args.range,
            data=data
        )
        print(f"Updated {result.get('updatedCells', 0)} cells")
        
    elif args.command == "sheets":
        # List all sheets in a spreadsheet
        result = client.list_sheets(spreadsheet_id=args.spreadsheet_id)
        print("Sheets:")
        for sheet in result:
            print(f"- {sheet}")
            
    elif args.command == "create-sheet":
        # Create a new sheet
        result = client.create_sheet(
            spreadsheet_id=args.spreadsheet_id,
            title=args.title
        )
        print(f"Created sheet: {result['title']}")
        print(f"Sheet ID: {result['sheetId']}")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
