# VIN Tool MCP Server

An MCP server for validating Vehicle Identification Numbers (VIN) and retrieving vehicle information using the NHTSA API.

## Features

- Validates VIN numbers
- Retrieves detailed vehicle information from the NHTSA database
- Returns structured data with vehicle specifications

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/vin-tool.git
cd vin-tool

# Install dependencies
uv pip install -e .
```

## Usage

### Running the Server

```bash
python main.py
```

### Using the MCP Tool

The MCP server exposes a `get_vehicle_info` tool that accepts a VIN number and returns vehicle information.

Example request:

```json
{
  "vin": "1HGCM82633A004352"
}
```

Example response:

```json
{
  "success": true,
  "vin": "1HGCM82633A004352",
  "vehicle_info": {
    "Make": "HONDA",
    "Model": "ACCORD",
    "Model Year": "2003",
    "Vehicle Type": "PASSENGER CAR",
    "Engine Number of Cylinders": "6",
    "Fuel Type - Primary": "Gasoline",
    "Transmission Style": "Automatic"
  },
  "raw_data": {
    // Full API response from NHTSA
  }
}
```

## API Reference

The tool uses the NHTSA Vehicle API:
- API Endpoint: `https://vpic.nhtsa.dot.gov/api/vehicles/decodevin/{vin}?format=json`
- Documentation: [NHTSA Vehicle API](https://vpic.nhtsa.dot.gov/api/)

## License

MIT