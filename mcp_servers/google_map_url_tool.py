import re
import urllib.parse
from typing import Union, Tuple, Optional
from pydantic.fields import FieldInfo
from pydantic import Field


def generate_google_maps_url(
        location: Union[str, Tuple[float, float]] = Field(
            description="Location description or coordinates. Can be: 1) Place description string (e.g. 'Eiffel Tower, Paris') 2) Latitude-longitude tuple (e.g. (48.858370, 2.294481)) 3) Coordinate string (e.g. '40.7128,-74.0060')",
            examples=["Eiffel Tower, Paris", (48.858370, 2.294481), "40.7128,-74.0060"]
        ),
        zoom: int = Field(
            description="Map zoom level (0-20), where 15 is a city-level view",
            default=15,
            ge=0,
            le=20
        ),
        parse_text_coordinates: bool = Field(
            description="Whether to attempt extracting coordinates from text descriptions",
            default=True
        )
) -> str:
    """
    Generates a Google Maps URL without requiring an API key

    This function accepts various formats of location input (place description, coordinate tuple, or coordinate string)
    and generates a Google Maps URL that can be opened directly in a browser.

    For text location descriptions, it generates a search URL;
    For coordinates, it generates a precise location URL.

    Args:
        location: Location information (text description, coordinate tuple, or coordinate string)
        zoom: Map zoom level (0-20)
        parse_text_coordinates: Whether to attempt extracting coordinates from text descriptions

    Returns:
        Google Maps URL string
    """
    # Handle coordinate tuple input
    if isinstance(location, tuple) and len(location) == 2:
        lat, lng = location
        if _validate_coordinates(lat, lng):
            return f"https://www.google.com/maps?q={lat},{lng}&z={zoom}"

    # Handle string input
    if isinstance(location, str):
        # Attempt to parse coordinates from the string
        if parse_text_coordinates:
            coords = _parse_coordinates_from_string(location)
            if coords:
                return f"https://www.google.com/maps?q={coords[0]},{coords[1]}&z={zoom}"

        # Attempt to handle as a coordinate string
        if "," in location:
            try:
                parts = location.split(",", 1)
                lat = float(parts[0].strip())
                lng = float(parts[1].strip())
                if _validate_coordinates(lat, lng):
                    return f"https://www.google.com/maps?q={lat},{lng}&z={zoom}"
            except ValueError:
                pass

        # Handle as a text description
        return f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(location)}"

    # Default to global view
    return "https://www.google.com/maps"


def _validate_coordinates(lat: float, lng: float) -> bool:
    """Validates whether latitude and longitude are within valid ranges"""
    return -90 <= lat <= 90 and -180 <= lng <= 180


def _parse_coordinates_from_string(input_str: str) -> Optional[Tuple[float, float]]:
    """
    Attempts to parse latitude and longitude from a string

    Supported formats:
    - 40.7128, -74.0060
    - (40.7128, -74.0060)
    - Lat: 40.7128, Lng: -74.0060
    - N 40.7128, W 74.0060
    """
    # Attempt to match common latitude-longitude formats
    patterns = [
        r"(-?\d+\.\d+),\s*(-?\d+\.\d+)",  # 40.7128, -74.0060
        r"\((-?\d+\.\d+),\s*(-?\d+\.\d+)\)",  # (40.7128, -74.0060)
        r"Lat:\s*(-?\d+\.\d+),\s*Lng:\s*(-?\d+\.\d+)",  # Lat: 40.7128, Lng: -74.0060
        r"([NS])\s*(\d+\.\d+),\s*([WE])\s*(\d+\.\d+)"  # N 40.7128, W 74.0060
    ]

    for pattern in patterns:
        match = re.search(pattern, input_str)
        if match:
            if len(match.groups()) == 2:
                try:
                    lat = float(match.group(1))
                    lng = float(match.group(2))
                    if _validate_coordinates(lat, lng):
                        return (lat, lng)
                except ValueError:
                    continue

            elif len(match.groups()) == 4:
                try:
                    ns = match.group(1)
                    lat_val = float(match.group(2))
                    ew = match.group(3)
                    lng_val = float(match.group(4))

                    lat = lat_val if ns.upper() == 'N' else -lat_val
                    lng = lng_val if ew.upper() == 'E' else -lng_val

                    if _validate_coordinates(lat, lng):
                        return (lat, lng)
                except ValueError:
                    continue

    return None


from oxygent import oxy
google_map_url = oxy.FunctionHub(name="google_map_url_tool", timeout=900)


@google_map_url.tool(description="Generates a Google Maps URL for a location without requiring an API key")
def generate_google_maps_url_api(
        location: Union[str, Tuple[float, float]] = Field(
            description="Location input. Can be: 1) Place description (e.g. 'Eiffel Tower, Paris') "
                        "2) Coordinate tuple (e.g. (48.858370, 2.294481)) "
                        "3) Coordinate string (e.g. '40.7128,-74.0060')",
            examples=["Eiffel Tower, Paris", (48.858370, 2.294481), "40.7128,-74.0060"]
        ),
        zoom: int = Field(
            description="Map zoom level (0-20), 15 is city-level view",
            default=15,
            ge=0,
            le=20
        ),
        parse_text_coordinates: bool = Field(
            description="Attempt to extract coordinates from text descriptions",
            default=True
        )
) -> str:
    """
    Generates a Google Maps URL for various location inputs

    This function accepts multiple location formats and generates a URL
    that can be opened directly in a browser to view the location on Google Maps.

    For text descriptions, it generates a search URL;
    For coordinates, it generates a precise location URL.
    """
    if isinstance(zoom, FieldInfo):
        zoom = zoom.default
    if isinstance(parse_text_coordinates, FieldInfo):
        parse_text_coordinates = parse_text_coordinates.default
    return generate_google_maps_url(location, zoom, parse_text_coordinates)


if __name__ == '__main__':
    # Using place description
    url1 = generate_google_maps_url("Eiffel Tower, Paris")
    print(url1)  # https://www.google.com/maps/search/?api=1&query=Eiffel%20Tower%2C%20Paris

    # Using coordinate tuple
    url2 = generate_google_maps_url((48.858370, 2.294481))
    print(url2)  # https://www.google.com/maps?q=48.85837,2.294481&z=15

    # Using coordinate string
    url3 = generate_google_maps_url("40.7128,-74.0060")
    print(url3)  # https://www.google.com/maps?q=40.7128,-74.006&z=15

    # Closer view
    url = generate_google_maps_url("Statue of Liberty", zoom=18)
    print(url)  # https://www.google.com/maps/search/?api=1&query=Statue%20of%20Liberty

    # Wider view
    url = generate_google_maps_url("New York City", zoom=10)
    print(url)

    # Text containing coordinates
    location_text = "Meeting location: Lat: 40.6892, Lng: -74.0445 (Statue of Liberty)"
    url = generate_google_maps_url(location_text)
    print(url)  # https://www.google.com/maps?q=40.6892,-74.0445&z=15

    # Complex format
    complex_text = "Gathering point: N 40.7484, W 73.9857 - Empire State Building"
    url = generate_google_maps_url(complex_text)
    print(url)  # https://www.google.com/maps?q=40.7484,-73.9857&z=15

    # Force text processing
    location_text = "40.7128,-74.0060"
    url = generate_google_maps_url(location_text, parse_text_coordinates=False)
    print(url)  # https://www.google.com/maps/search/?api=1&query=40.7128%2C-74.0060
    url = generate_google_maps_url("the New Jersey side of the Lincoln Tunnel", zoom=18)
    print(url)