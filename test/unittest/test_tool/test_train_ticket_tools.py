import pytest
from datetime import datetime, timedelta
from oxygent.preset_tools.train_ticket_tools import get_stations
from oxygent.preset_tools.train_ticket_tools import get_tickets
from oxygent.preset_tools.train_ticket_tools import get_stations_of_city
from oxygent.preset_tools.train_ticket_tools import get_cookie


def test_get_stations():
    # 调用被测试函数
    result = get_stations()

    # 验证结果
    assert len(result) > 0
    assert 'BJP' in result


def test_get_cookie():
    # 调用被测试函数
    result = get_cookie()
    print(result)

    # 验证结果
    assert len(result) > 0
    assert result['Set-Cookie']


@pytest.mark.asyncio
async def test_get_stations_of_city_single_city():
    # 调用被测试函数
    result = await get_stations_of_city('广州')
    print(result)

    # 验证结果
    assert len(result['广州'])


@pytest.mark.asyncio
async def test_get_stations_of_city_multiple_cities():
    # 调用被测试函数
    result = await get_stations_of_city('广州|西安')
    print(result)

    # 验证结果
    assert len(result['广州']) and len(result['西安'])


@pytest.mark.asyncio
async def test_get_tickets_empty_result():
    # 获取后天的日期，格式为 "%Y-%m-%d"
    day_after_tomorrow = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
    # 调用被测试函数
    result = await get_tickets(day_after_tomorrow, 'BJP', 'SHH','ADULT')
    print(result)

    # 验证结果
    assert len(result) > 0

