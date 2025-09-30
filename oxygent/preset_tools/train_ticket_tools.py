import re
import json
import datetime
import requests
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta
from oxygent.oxy import FunctionHub

train_ticket_tools = FunctionHub(name="train_ticket_tools")


class StationData(BaseModel):
    """车站息模型"""
    station_id: Optional[str] = Field(None, description="station_id")
    station_name: str = Field(..., description="车站名称station_name")
    station_code: str = Field(..., description="车站代码station_code")
    station_pinyin: str = Field(..., description="拼音")
    station_short: str = Field(..., description="拼音简写")
    station_index: Optional[str] = Field(None, description="station_index")
    code: Optional[str] = Field(None, description="车站编号")
    city: Optional[str] = Field(None, description="所属城市")


class Ticket(BaseModel):
    """车票信息模型"""
    train_no: str = Field(..., description="车次")
    from_station_name: str = Field(..., description="出发站名")
    to_station_name: str = Field(..., description="到达站名")
    start_time: str = Field(..., description="出发时间")
    arrive_time: str = Field(..., description="到达时间")
    duration: str = Field(..., description="历时")
    can_web_buy: str = Field(..., description="是否可购买")

    # 座位信息
    business_seat_price: Optional[str] = Field(None, description="商务座价格")
    first_class_price: Optional[str] = Field(None, description="一等座价格")
    second_class_price: Optional[str] = Field(None, description="二等座价格")
    soft_sleeper_price: Optional[str] = Field(None, description="软卧价格")
    hard_sleeper_price: Optional[str] = Field(None, description="硬卧价格")
    soft_seat_price: Optional[str] = Field(None, description="软座价格")
    hard_seat_price: Optional[str] = Field(None, description="硬座价格")
    no_seat_price: Optional[str] = Field(None, description="无座价格")

    # 余票信息
    business_seat_num: Optional[str] = Field(None, description="商务座余票")
    first_class_num: Optional[str] = Field(None, description="一等座余票")
    second_class_num: Optional[str] = Field(None, description="二等座余票")
    soft_sleeper_num: Optional[str] = Field(None, description="软卧余票")
    hard_sleeper_num: Optional[str] = Field(None, description="硬卧余票")
    soft_seat_num: Optional[str] = Field(None, description="软座余票")
    hard_seat_num: Optional[str] = Field(None, description="硬座余票")
    no_seat_num: Optional[str] = Field(None, description="无座余票")


@train_ticket_tools.tool(description="通过中文城市名查询代表该城市的 `station_code`。"
                                     "此接口主要用于在用户提供**城市名**作为出发地或到达地时，为接口准备`station_code` 参数。")
def get_stations_of_city(
        city_names: str = Field(..., description='要查询的城市，比如"西安"。若要查询多个城市，请用|分割，比如"北京|西安')
) -> Dict[str, List[StationData]]:

    stations = get_stations()
    # 将城市名按|分割成列表
    city_list = city_names.split('|')
    # 创建结果字典，键为城市名，值为该城市的车站列表
    result: Dict[str, List[StationData]] = {}
    # 初始化结果字典中的城市键对应的空列表
    for city in city_list:
        result[city] = []
    # 遍历所有车站，将符合条件的车站添加到对应城市的列表中
    for station_data in stations.values():
        station_city = station_data.city
        # 如果车站所在城市在查询列表中，则添加到结果中
        if station_city in city_list:
            result[station_city].append(station_data)

    return result


@train_ticket_tools.tool(description="查询车票信息")
def get_tickets(
        train_date: str = Field(..., description='查询日期，格式为 `yyyy-MM-dd`。如果用户提供的是相对日期（如“明天”），'
                                                 '请务必先调用 `get_current_date` 接口获取当前日期，并计算出目标日期。'),
        from_station_code: str = Field(..., description="出发地的 `station_code`，必须是通过 `get_stations_of_city` 接口"
                                                        "查询得到的车站代码，严禁直接使用中文地名。"),
        to_station_code: str = Field(..., description="到达地的 `station_code`，必须是通过 `get_stations_of_city` 接口"
                                                      "查询得到的车站代码，严禁直接使用中文地名。"),
        purpose_codes: str = Field(default="ADULT", description="乘客类型")
) -> List[Ticket]:

    url = (f"https://kyfw.12306.cn/otn/leftTicket/queryG?"
           f"leftTicketDTO.train_date={train_date}"
           f"&leftTicketDTO.from_station={from_station_code}"
           f"&leftTicketDTO.to_station={to_station_code}"
           f"&purpose_codes={purpose_codes}")
    # 构造请求Header
    raw_cookie = get_cookie()
    cookie = format_cookies(raw_cookie)
    headers = {'Cookie': cookie}
    # 查询车票信息
    res = requests.get(url, headers=headers).text
    res_json = json.loads(res)
    result = res_json['data']['result']
    # 解析车票数据
    tickets = _parse_tickets(ticket_data=result)

    return tickets


@train_ticket_tools.tool(description="获取当前日期，以上海时区（Asia/Shanghai, UTC+8）为准，返回格式为 `yyyy-MM-dd`。"
                                     "主要用于解析用户提到的相对日期（如“明天”、“下周三”），为其他需要日期的接口提供准确的日期输入。")
def get_current_date() -> str:
    utc_now = datetime.now(timezone.utc)
    shanghai_tz = timezone(timedelta(hours=8))
    shanghai_now = utc_now.astimezone(shanghai_tz)
    formatted_date = shanghai_now.strftime("%Y-%m-%d")

    return formatted_date


def get_stations() -> Dict[str, StationData]:
    """
    从12306网站获取并解析所有火车站数据

    Returns:
        以车站代码为键的车站数据字典

    Raises:
        Exception: 当无法获取或解析车站数据时抛出异常
    """
    # 获取网站HTML内容
    main_page_url = 'https://www.12306.cn/index/'
    try:
        html = requests.get(main_page_url).text
    except Exception as error:
        raise Exception(f"[Error]: Get the main page HTML failed.{error}")

    # 提取站名JS文件路径
    match = re.search(r'(/script/core/common/station_name.+?\.js)', html)
    if match is None:
        raise Exception('[Error]: Get station name js file failed.')

    # 获取站名JS文件
    station_name_js_file_path = match.group(0)
    try:
        station_name_js = requests.get(main_page_url + station_name_js_file_path).text
    except Exception as error:
        raise Exception(f"[Error]: Get the main page HTML failed.{error}")

    # 提取站名原始数据
    raw_data_match = re.search(r"var station_names ='(.+?)'", station_name_js)
    if raw_data_match is None:
        raise Exception('[Error]: Extract station data failed.')

    raw_data = raw_data_match.group(1)
    stations_data = parse_stations_data(raw_data)

    return stations_data


def parse_stations_data(raw_data: str) -> Dict[str, StationData]:
    """
    将原始车站数据字符串解析为结构化的字典

    Args:
        raw_data: 包含车站信息的竖线分隔字符串

    Returns:
        以车站代码为键，车站数据为值的字典
    """
    result: Dict[str, StationData] = {}
    data_array = raw_data.split('|')
    data_list = []

    # 将数据按10个一组分组（每组代表一个车站）
    for i in range(len(data_array) // 10):
        data_list.append(data_array[i * 10:(i * 10) + 10])

    # 处理每个车站数据组
    for group in data_list:
        # 如果车站代码为空，跳过
        if not group[2]:
            continue

        station = StationData(
            station_id=group[0],
            station_name=group[1],
            station_code=group[2],
            station_pinyin=group[3],
            station_short=group[4],
            station_index=group[5],
            code=group[6],
            city=group[7]
        )

        # 使用车站代码作为键，将车站添加到结果字典中
        result[station.station_code] = station  # type: ignore

    return result


def format_cookies(cookies):
    """
    将cookie字典转换为字符串格式

    Args:
        cookies: Cookie字典

    Returns:
        str: 格式化后的cookie字符串，如 'key1=value1; key2=value2'
    """
    return '; '.join([f"{key}={value}" for key, value in cookies.items()])


def get_cookie():
    """
    从12306网站获取cookie

    Returns:
        dict: Cookie字典，如果请求失败则返回None
    """
    url = "https://kyfw.12306.cn/otn/leftTicket/init"
    try:
        response = requests.get(url)
        return response.headers
    except Exception as error:
        print(f"[Error]: Get 12306 cookie failed. {error}")
        return None


def _parse_tickets(ticket_data: List[str]) -> List[Ticket]:
    """解析车票数据"""
    tickets = []

    for ticket_str in ticket_data:
        try:
            # 12306返回的数据格式是用|分隔的字符串
            parts = ticket_str.split('|')

            if len(parts) < 35:  # 确保有足够的字段
                continue

            ticket = Ticket(
                train_no=parts[3],  # 车次
                from_station_name=parts[6],  # 出发站
                to_station_name=parts[7],  # 到达站
                start_time=parts[8],  # 出发时间
                arrive_time=parts[9],  # 到达时间
                duration=parts[10],  # 历时
                can_web_buy=parts[11],  # 是否可购买

                # 票价信息（暂为None，后续可补充真实票价）
                business_seat_price=None,
                first_class_price=None,
                second_class_price=None,
                soft_sleeper_price=None,
                hard_sleeper_price=None,
                soft_seat_price=None,
                hard_seat_price=None,
                no_seat_price=None,

                # 余票信息 - 根据12306实际字段位置调整
                business_seat_num=parts[32] if parts[32] != '' else None,  # 商务座余票
                first_class_num=parts[31] if parts[31] != '' else None,  # 一等座余票
                second_class_num=parts[30] if parts[30] != '' else None,  # 二等座余票
                soft_sleeper_num=parts[23] if parts[23] != '' else None,  # 软卧余票
                hard_sleeper_num=parts[28] if parts[28] != '' else None,  # 硬卧余票
                soft_seat_num=parts[24] if parts[24] != '' else None,  # 软座余票
                hard_seat_num=parts[29] if parts[29] != '' else None,  # 硬座余票
                no_seat_num=parts[26] if parts[26] != '' else None,  # 无座余票
            )

            tickets.append(ticket)

        except (IndexError, ValueError) as error:
            print(f"[Error]: Parse ticket data failed. {error}")
            continue

    return tickets
