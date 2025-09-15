import json
import platform
import psutil
import asyncio
from pydantic import Field
from oxygent.oxy import FunctionHub

system_tools = FunctionHub(name="system_tools")


@system_tools.tool(
    description="Get system information including OS, architecture, and Python version"
)
async def get_system_info() -> str:
    """
    获取系统信息
    """
    info = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "architecture": platform.architecture()[0],
        "python_version": platform.python_version(),
        "node": platform.node(),
    }
    return json.dumps(info, ensure_ascii=False)


@system_tools.tool(
    description="Get current system resource usage including CPU, memory, and disk usage"
)
async def get_system_usage() -> str:
    """
    获取系统资源使用情况
    """
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        usage = {
            "cpu_percent": cpu_percent,
            "memory_total_gb": round(memory.total / (1024**3), 2),
            "memory_available_gb": round(memory.available / (1024**3), 2),
            "memory_percent": memory.percent,
            "disk_total_gb": round(disk.total / (1024**3), 2),
            "disk_used_gb": round(disk.used / (1024**3), 2),
            "disk_free_gb": round(disk.free / (1024**3), 2),
            "disk_percent": round(disk.used / disk.total * 100, 2)
        }
        return json.dumps(usage, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

async def main():
    """
    主函数，用于测试系统工具的效果
    """
    print("=== 系统信息测试 ===")
    system_info_result = await get_system_info()  # 添加 await
    print("系统信息:")
    print(system_info_result)

    # 将JSON字符串转换为字典以便更清晰地显示
    try:
        system_info_dict = json.loads(system_info_result)
        print("\n格式化系统信息:")
        for key, value in system_info_dict.items():
            print(f"  {key}: {value}")
    except json.JSONDecodeError:
        print("无法解析系统信息JSON")

    print("\n=== 系统资源使用情况测试 ===")
    usage_result = await get_system_usage()  # 添加 await
    print("资源使用情况:")
    print(usage_result)

    # 将JSON字符串转换为字典以便更清晰地显示
    try:
        usage_dict = json.loads(usage_result)
        print("\n格式化资源使用情况:")
        if "error" in usage_dict:
            print(f"获取资源使用情况时出错: {usage_dict['error']}")
        else:
            for key, value in usage_dict.items():
                print(f"  {key}: {value}")
    except json.JSONDecodeError:
        print("无法解析资源使用情况JSON")



if __name__ == "__main__":
    asyncio.run(main())
