import json
import requests
from fastmcp import FastMCP
from typing import Dict, Any

app = FastMCP()

@app.tool("get_vehicle_info")
async def get_vehicle_info(vin: str) -> Dict[str, Any]:
    """
    Get vehicle information by VIN number.
    
    Args:
        vin: The Vehicle Identification Number to look up
        
    Returns:
        Vehicle information from the NHTSA database
    """
    if not vin:
        return {
            "success": False,
            "error": "VIN number is required"
        }
    
    try:
        # Call the NHTSA API to decode the VIN
        api_url = f"https://vpic.nhtsa.dot.gov/api/vehicles/decodevin/{vin}?format=json"
        response = requests.get(api_url)
        response.raise_for_status()
        
        data = response.json()
        
        # Check if the API returned valid data
        if data.get("Results"):
            # Extract relevant vehicle information
            vehicle_info = {}
            for result in data["Results"]:
                if result.get("Value") and result.get("Value") != "Not Applicable":
                    vehicle_info[result["Variable"]] = result["Value"]
            
            return {
                "success": True,
                "vin": vin,
                "vehicle_info": vehicle_info,
                "raw_data": data
            }
        else:
            return {
                "success": False,
                "error": "No information found for the provided VIN"
            }
    
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"API request failed: {str(e)}"
        }

def main():
    app.run()


if __name__ == "__main__":
    main()
