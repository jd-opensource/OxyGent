from oxygent.oxy import FunctionHub
from pydantic import Field

time_tools = FunctionHub(name="time_tools")


@time_tools.tool(description="Get current time in a specific timezones")
def get_current_time(
    timezone: str = Field(
        description="IANA timezone name (e.g., 'America/New_York', 'Europe/London'). Use 'Asia/Shanghai' as local timezone if no timezone provided by the user. "
    ),
) -> str:
    from pytz import timezone as pytimezone
    from datetime import datetime

    if timezone is None:
        timezone = "Asia/Shanghai"

    tz = pytimezone(timezone)
    now = datetime.now(tz)
    return str(now.strftime("%Y-%m-%d %H:%M:%S %Z%z"))


@time_tools.tool(description="Convert time between timezones")
def convert_time(
    source_timezone: str = Field(
        description="Source IANA timezone name (e.g., 'America/New_York', 'Europe/London'). Use 'Asia/Shanghai' as local timezone if no source timezone provided by the user."
    ),
    time: str = Field(description="Time to convert in 24-hour format (HH:MM)"),
    target_timezone: str = Field(
        description="Target IANA timezone name (e.g., 'Asia/Tokyo', 'America/San_Francisco'). Use 'Asia/Shanghai' as local timezone if no target timezone provided by the user."
    ),
) -> str:
    from datetime import datetime
    import pytz

    dt = datetime.strptime(time, "%H:%M")
    # Create timezone objects for the source and target timezones
    src_tz = pytz.timezone(source_timezone)
    dst_tz = pytz.timezone(target_timezone)
    # Localize the datetime object to the source timezone
    src_dt = src_tz.localize(dt)
    # Convert the datetime object to the target timezone
    dst_dt = src_dt.astimezone(dst_tz)
    # Format the converted datetime object as a string
    converted_time = dst_dt.strftime("%H:%M")
    return str(converted_time)
