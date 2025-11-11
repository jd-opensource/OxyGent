import asyncio
import os
import json
import base64
from io import BytesIO
from typing import List, Dict, Any, Optional
from pydantic import Field, BaseModel
from PIL import Image
import logging
from oxygent import MAS, oxy, OxyRequest
from oxygent.utils.common_utils import image_to_base64
import time
import re
from zai import ZhipuAiClient
from test_unstructured.staging.test_label_box import attachment




# 定义食物营养数据库
FOOD_NUTRITION_DB = {
    "苹果": {"calories_per_100g": 52, "protein": 0.3, "fat": 0.2, "carbs": 13.8, "fiber": 2.4},
    "香蕉": {"calories_per_100g": 89, "protein": 1.1, "fat": 0.3, "carbs": 22.8, "fiber": 2.6},
    "橙子": {"calories_per_100g": 47, "protein": 0.9, "fat": 0.1, "carbs": 11.8, "fiber": 2.4},
    "草莓": {"calories_per_100g": 32, "protein": 0.7, "fat": 0.3, "carbs": 7.7, "fiber": 2.0},
    "西瓜": {"calories_per_100g": 30, "protein": 0.6, "fat": 0.2, "carbs": 7.6, "fiber": 0.4},
    "面包": {"calories_per_100g": 265, "protein": 9.0, "fat": 3.2, "carbs": 49.0, "fiber": 2.7},
    "米饭": {"calories_per_100g": 130, "protein": 2.7, "fat": 0.3, "carbs": 28.0, "fiber": 0.4},
    "面条": {"calories_per_100g": 138, "protein": 5.0, "fat": 2.0, "carbs": 25.0, "fiber": 1.2},
    "牛肉": {"calories_per_100g": 250, "protein": 26.0, "fat": 17.0, "carbs": 0.0, "fiber": 0.0},
    "鸡肉": {"calories_per_100g": 165, "protein": 31.0, "fat": 3.6, "carbs": 0.0, "fiber": 0.0},
    "鱼": {"calories_per_100g": 206, "protein": 22.0, "fat": 12.0, "carbs": 0.0, "fiber": 0.0},
    "鸡蛋": {"calories_per_100g": 155, "protein": 12.6, "fat": 11.0, "carbs": 1.1, "fiber": 0.0},
    "牛奶": {"calories_per_100g": 42, "protein": 3.4, "fat": 1.0, "carbs": 5.0, "fiber": 0.0},
    "奶酪": {"calories_per_100g": 402, "protein": 25.0, "fat": 33.0, "carbs": 1.3, "fiber": 0.0},
    "酸奶": {"calories_per_100g": 59, "protein": 3.5, "fat": 3.3, "carbs": 4.7, "fiber": 0.0},
    "土豆": {"calories_per_100g": 77, "protein": 2.0, "fat": 0.1, "carbs": 17.0, "fiber": 2.2},
    "胡萝卜": {"calories_per_100g": 41, "protein": 0.9, "fat": 0.2, "carbs": 9.6, "fiber": 2.8},
    "西兰花": {"calories_per_100g": 34, "protein": 2.8, "fat": 0.4, "carbs": 6.6, "fiber": 2.6},
    "菠菜": {"calories_per_100g": 23, "protein": 2.9, "fat": 0.4, "carbs": 3.6, "fiber": 2.2},
    "番茄": {"calories_per_100g": 18, "protein": 0.9, "fat": 0.2, "carbs": 3.9, "fiber": 1.2},
}

web_search_tools = oxy.FunctionHub(name="web_search_tools")

@web_search_tools.tool(description="网络搜索食物热量和营养成分")
async def web_search(food_name: str = Field(description="需要查询营养成分的食物名称")) -> str:
    print(f"[Web Search MCP] Received request for: {food_name}")

    client = ZhipuAiClient(api_key=os.getenv("DEFAULT_LLM_API_KEY"))

    response = client.web_search.web_search(
        search_engine="search_pro",
        search_query="搜索" + food_name + "的营养，包括每百克热量，蛋白质、脂肪、碳水化合物和纤维素",
        count=3,  # 返回结果的条数，范围1-50，默认10
        search_recency_filter="noLimit",  # 搜索指定日期范围内的内容
        content_size="medium"  # 控制网页摘要的字数，默认medium
    )

    return response.search_result

calorie_calculation_tools = oxy.FunctionHub(name="calorie_calculation_tools")
@calorie_calculation_tools.tool(description="计算食物热量和营养成分")
async def calculate_calories(food_items: List[Dict[str, Any]] = Field(description="食物列表，包含名称和重量")):
    """计算食物的热量和营养成分"""
    try:
        total_calories = 0
        total_protein = 0
        total_fat = 0
        total_carbs = 0
        total_fiber = 0
        results = []

        for food in food_items:
            food_name = food["name"]
            weight = food["weight"]

            if food_name in FOOD_NUTRITION_DB:
                data = FOOD_NUTRITION_DB[food_name]
                calories = (data["calories_per_100g"] * weight) / 100
                protein = (data["protein"] * weight) / 100
                fat = (data["fat"] * weight) / 100
                carbs = (data["carbs"] * weight) / 100
                fiber = (data["fiber"] * weight) / 100 if "fiber" in data else 0

                total_calories += calories
                total_protein += protein
                total_fat += fat
                total_carbs += carbs
                total_fiber += fiber

                results.append({
                    "name": food_name,
                    "weight": weight,
                    "calories": round(calories, 2),
                    "protein": round(protein, 2),
                    "fat": round(fat, 2),
                    "carbs": round(carbs, 2),
                    "fiber": round(fiber, 2)
                })
            else:
                # 如果食物不在数据库中，使用默认值或跳过
                results.append({
                    "name": food_name,
                    "weight": weight,
                    "calories": "未知",
                    "protein": "未知",
                    "fat": "未知",
                    "carbs": "未知",
                    "fiber": "未知",
                    "note": "该食物在数据库中不存在"
                })

        return {
            "food_items": results,
            "total_calories": round(total_calories, 2),
            "total_protein": round(total_protein, 2),
            "total_fat": round(total_fat, 2),
            "total_carbs": round(total_carbs, 2),
            "total_fiber": round(total_fiber, 2),
            "summary": f"总共检测到 {len(results)} 种食物，总热量为 {round(total_calories, 2)} 千卡"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"热量计算失败: {str(e)}"
        }


class FoodItem(BaseModel):
    """Represents a single food item with its name and weight."""
    name: str = Field(description="食物的名称，例如：'米饭', '土豆炖牛肉'。")
    weight: float = Field(description="食物的重量，单位是克（g）。如果用户输入了'公斤'或'kg'，请转换为克。如果用户使用了量词如'一个'、'一碗'，请估算一个合理的重量。例如：一个苹果约150克，一碗米饭约200克。")


# 创建营养建议工具
nutrition_advice_tools = oxy.FunctionHub(name="nutrition_advice_tools")


@nutrition_advice_tools.tool(description="根据食物热量和营养成分提供饮食建议")
async def provide_nutrition_advice(nutrition_data: Dict[str, Any] = Field(description="食物的营养数据")):
    """根据食物热量和营养成分提供饮食建议"""
    try:
        total_calories = nutrition_data.get("total_calories", 0)
        total_protein = nutrition_data.get("total_protein", 0)
        total_fat = nutrition_data.get("total_fat", 0)
        total_carbs = nutrition_data.get("total_carbs", 0)
        total_fiber = nutrition_data.get("total_fiber", 0)

        # 根据营养成分提供建议
        advice = []

        if total_calories > 800:
            advice.append("这顿饭的热量较高，建议减少食用量或选择低热量的替代食品。")
        elif total_calories < 300:
            advice.append("这顿饭的热量较低，可能不足以满足身体需求，建议适当增加食物摄入。")
        else:
            advice.append("这顿饭的热量适中，符合一般成人单餐热量需求。")


        if total_protein < 15:
            advice.append("蛋白质摄入偏低，建议增加瘦肉、鱼、蛋、豆类等富含蛋白质的食物。")
        else:
            advice.append("蛋白质摄入充足，有助于维持肌肉健康。")


        if total_fat > 30:
            advice.append("脂肪摄入偏高，建议减少油脂类食物的摄入，选择低脂烹饪方式。")


        if total_carbs > 100:
            advice.append("碳水化合物摄入较多，建议控制主食量，增加蔬菜摄入。")


        if total_fiber < 5:
            advice.append("膳食纤维摄入不足，建议增加蔬菜、水果、全谷物的摄入。")

        return {
            "advice": advice,
            "summary": "\n".join(advice)
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"提供营养建议失败: {str(e)}"
        }

async def master_workflow(oxy_request: OxyRequest):
    query = oxy_request.get_query()

    # 调用 food_parsing_agent 解析食物
    food_parsing_response = await oxy_request.call(
        callee='food_parsing_agent',
        arguments={'query':"你是一个JSON生成器。你的唯一任务是从用户输入中提取食物信息并以JSON格式输出。"
        "**绝对不要**输出任何JSON以外的文本、解释或注释。只返回JSON对象。"
        "JSON对象必须包含一个 'food_items' 键，其值为一个食物对象列表。"
        "每个食物对象都必须包含 'name' (字符串) 和 'weight' (数字, 单位为克) 两个字段。"
        "如果用户使用了'一个'、'一碗'等量词，请估算一个合理的重量（例如：一个苹果约150克，一碗米饭约200克）。"
        "如果用户没有提供明确的食物信息，请返回一个空的 'food_items' 列表。"
        "示例输入: '我早餐吃了一个苹果和200克面包'"
        "示例输出: {\"food_items\": [{\"name\": \"苹果\", \"weight\": 150}, {\"name\": \"面包\", \"weight\": 200}]}"
        "示例输入: '今天天气怎么样'"
        "示例输出: {\"food_items\": []}"
        "现在，请处理以下用户输入：" + query}
    )

    # 从子智能体的响应中获取输出
    food_parsing_result_str = food_parsing_response.output

    try:
        try:
            food_parsing_result = json.loads(food_parsing_result_str)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', food_parsing_result_str, re.DOTALL)
            if not match:
                return f"解析食物信息失败，无法从子智能体返回中找到有效的JSON内容。返回内容：{food_parsing_result_str}"
            json_str = match.group(0)
            food_parsing_result = json.loads(json_str)

    except (json.JSONDecodeError, TypeError):
        return f"解析食物信息失败，无法解析子智能体返回的JSON字符串。返回内容：{food_parsing_result_str}"

    food_items = food_parsing_result.get('food_items', [])

    if not food_items:
        return "无法从您的描述中解析出有效的食物信息，请提供更详细的描述。"

    unknown_foods = [item for item in food_items if item['name'] not in FOOD_NUTRITION_DB]

    if unknown_foods:
        # 对未知食物进行网络搜索
        for food_item in unknown_foods:
            food_name = food_item['name']
            # 调用新的搜索智能体
            search_response = await oxy_request.call(
                callee='food_nutrition_search_agent',
                arguments={'query':"你是一个JSON生成器。你的唯一任务是使用工具在网上查找食物的营养成分并将结果以JSON格式输出,并且无需输出其他内容。"
                    "你的任务是根据提供的食物名称，通过网络搜索工具返回的结果找到它每100克的营养成分，"
                    "包括热量(calories_per_100g)、蛋白质(protein)、脂肪(fat)、碳水化合物(carbs)和纤维素（fiber）。"
                    "请以JSON格式返回结果。"
                    "例如，输入'牛油果'，应返回类似 `{\"calories_per_100g\": 160, \"protein\": 2.0, \"fat\": 15.0, \"carbs\": 9.0, \"fiber\": 1.5}` 的JSON对象。"
                    "如果有营养成分缺失的情况，则以默认值0.0来代替。"
                    "现在，请返回以下食物的营养成分：" + food_name}, 

            )

            try:
                # 解析返回的营养信息JSON
                nutrition_data = json.loads(search_response.output)
                # 验证数据并动态更新到FOOD_NUTRITION_DB
                if all(k in nutrition_data for k in ['calories_per_100g', 'protein', 'fat', 'carbs']):
                    FOOD_NUTRITION_DB[food_name] = nutrition_data
                else:
                    # 如果搜索结果不完整，可以记录日志或跳过
                    print(f"Warning: Incomplete nutrition data for {food_name} from web search.")
            except (json.JSONDecodeError, TypeError):
                print(f"Warning: Failed to parse nutrition data for {food_name} from web search.")

    # 调用 calorie_calculation_agent 计算热量
    calories_response = await oxy_request.call(
        callee='calculate_calories',
        arguments={'food_items': food_items}
    )
    nutrition_data = calories_response.output

    if not nutrition_data or 'total_calories' not in nutrition_data:
        return f"计算食物热量失败。返回内容: {nutrition_data}"

    # 调用 provide_nutrition_advice 工具提供建议
    advice_response = await oxy_request.call(
        callee='provide_nutrition_advice',
        arguments={'nutrition_data': nutrition_data}
    )
    advice_data = advice_response.output

    # 整合结果并返回
    final_response = {
        "nutrition_analysis": nutrition_data,
        "dietary_advice": advice_data
    }

    return json.dumps(final_response, ensure_ascii=False, indent=2)


#  Food Parsing Agent 
food_parsing_agent = oxy.ChatAgent( 
    name="food_parsing_agent",
    desc="一个JSON生成器。唯一任务是从用户输入中提取食物信息并以JSON格式输出",
    llm_model="default_llm",
    verbose=True
)

# --- 注册网络搜索智能体 ---
food_nutrition_search_agent = oxy.ReActAgent(
    name="food_nutrition_search_agent",
    desc="一个专门负责通过网络搜索获取特定食物营养成分的智能体。",
    llm_model="free_llm",
    max_react_rounds=1,
    tools=["web_search_tools"]
)

#Master Agent (主智能体)
master_agent = oxy.WorkflowAgent(
    name="master_agent",
    is_master=True,
    sub_agents=["food_parsing_agent", "food_nutrition_search_agent"], 
    tools=["calorie_calculation_tools", "nutrition_advice_tools"], 
    func_workflow=master_workflow,
    llm_model="default_llm",
    verbose=True
)

oxy_space = [
    oxy.HttpLLM(
        name="default_llm",
        api_key=os.getenv("DEFAULT_LLM_API_KEY"),
        base_url=os.getenv("DEFAULT_LLM_BASE_URL"),
        model_name=os.getenv("DEFAULT_LLM_MODEL_NAME"),
        headers=lambda _: {"Content-Type": "application/json"},
    ),
    oxy.HttpLLM(
        name="free_llm",
        api_key=os.getenv("DEFAULT_LLM_API_KEY"),
        base_url=os.getenv("DEFAULT_LLM_BASE_URL"),
        model_name=os.getenv("DEFAULT_LLM_MODEL_NAME"),
        headers=lambda _: {"Content-Type": "application/json"},
    ),
    calorie_calculation_tools,
    nutrition_advice_tools,
    food_parsing_agent,
    food_nutrition_search_agent, 
    master_agent, 
    web_search_tools
]


async def main():
    """主函数"""
    async with MAS(oxy_space=oxy_space) as mas:
        # 启动Web服务，让用户通过聊天界面输入
        await mas.start_web_service(
            first_query="一个苹果和200克的土豆炖牛肉和一盘番茄炒蛋",
            welcome_message="欢迎使用食物热量计算智能体！请输入食物名称和重量，我将为您计算热量。",
        )


if __name__ == "__main__":
    asyncio.run(main())


