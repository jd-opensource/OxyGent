import os
import subprocess
import json
from typing import Dict
from dashscope import MultiModalConversation
import dashscope
from oxygent.oxy import FunctionHub

video_understanding_tools = FunctionHub(name="video_understanding_tools")

# ✅ 设置 API Key（建议改为环境变量）
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")


import os
import subprocess

import os
import subprocess

def compress_video(input_path: str, max_size_mb: int = 100) -> str:
    """
    如果视频超过 max_size_mb（默认100MB），截取前15分钟输出新文件。
    """
    file_size_mb = os.path.getsize(input_path) / (1024 * 1024)
    if file_size_mb <= max_size_mb:
        print(f"✅ 文件大小 {file_size_mb:.2f}MB，小于 {max_size_mb}MB，无需压缩。")
        return input_path

    print(f"⚠️ 文件大小 {file_size_mb:.2f}MB，超过 {max_size_mb}MB，截取前15分钟...")

    output_path = os.path.splitext(input_path)[0] + "_cut15min.mp4"

    # ffmpeg 截取前 15 分钟 (不重新编码： -c copy)
    command = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-t", "00:15:00",   # 截取 15 分钟
        "-c", "copy",       # 不重新编码，保持原质量
        output_path
    ]

    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if not os.path.exists(output_path):
        print("❌ 截取失败，返回原文件")
        return input_path

    new_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"🎞️ 截取完成：{file_size_mb:.2f}MB → {new_size_mb:.2f}MB -> {output_path}")
    return output_path


import os
import subprocess
import json
from dashscope import MultiModalConversation


import os
import subprocess
import json
from dashscope import MultiModalConversation

@video_understanding_tools.tool(
    description="Understand a video file using Qwen3-VL-Plus model (auto-split into 10-minute parts)."
)
def understand_video(video_path: str, query_text: str, fps: int = 2) -> str:
    """
    使用 Qwen3-VL-Plus 模型理解视频内容。
    如果视频长度超过10分钟，则按每10分钟分割成多段分别理解并拼接结果。

    参数：
        video_path: 本地视频路径
        query_text: 用户指令，例如“请总结视频主要内容”
        fps: 每秒抽帧数量（默认2）

    返回：
        模型输出 JSON 字符串
    """

    def get_video_duration(input_path: str) -> float:
        """获取视频时长（秒）"""
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", input_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        try:
            return float(result.stdout.strip())
        except:
            raise ValueError("无法读取视频时长")

    def split_video_by_minutes(input_path: str, minutes: int = 10, output_dir="temp_splits") -> list:
        """按分钟分割视频，每段长度为 minutes 分钟"""
        os.makedirs(output_dir, exist_ok=True)
        duration = get_video_duration(input_path)
        segment_length = minutes * 60  # 转换为秒
        parts = []
        start = 0
        idx = 1

        while start < duration:
            part_file = os.path.join(output_dir, f"part_{idx}.mp4")
            cmd = [
                "ffmpeg", "-y", "-ss", str(start), "-i", input_path,
                "-t", str(segment_length), "-c", "copy", part_file
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            parts.append(part_file)
            start += segment_length
            idx += 1

        print(f"📽️ 已将视频分割为 {len(parts)} 段，每段约 {minutes} 分钟。")
        return parts

    def call_model(video_file, query_text, fps):
        """调用 Qwen3-VL-Plus 理解单个视频"""
        video_uri = f"file://{video_file}"
        messages = [{
            "role": "user",
            "content": [
                {"video": video_uri, "fps": fps},
                {"text": query_text}
            ]
        }]
        print(f"🚀 调用模型 qwen3-vl-plus 分析 {os.path.basename(video_file)} ...")

        try:
            response = MultiModalConversation.call(model="qwen3-vl-plus", messages=messages)
        except Exception as e:
            print(f"❌ 模型调用异常：{e}")
            return f"⚠️ 模型调用异常：{e}"

        if response is None:
            print("❌ 未收到模型响应（response=None）")
            return "⚠️ 模型未返回任何结果"

        # 打印完整响应结构以便调试
        print("🧩 模型原始响应：", response)

        try:
            if isinstance(response, dict) and "output" in response and "choices" in response["output"]:
                return response["output"]["choices"][0]["message"]["content"][0]["text"]
            else:
                return f"⚠️ 无法解析模型输出结构，response: {response}"
        except Exception as e:
            return f"⚠️ 解析模型输出时出错：{e}"

    try:
        # 分割视频（每10分钟一段）
        parts = split_video_by_minutes(video_path, minutes=10)

        # 分别理解每个片段
        results = []
        for i, part in enumerate(parts):
            part_result = call_model(part, f"{query_text}（第{i + 1}部分）", fps)
            results.append(part_result)

        # 拼接所有部分结果
        final_result = "\n".join([f"第{i+1}部分结果：{r}" for i, r in enumerate(results)])
        print("✅ 所有片段分析完成。")

        return json.dumps({"status": "success", "result": final_result}, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": e}, ensure_ascii=False)




import asyncio
if __name__ == "__main__":
    async def main():
        video_file = "/home/caotiezheng/pythoncode/OxyGent-main/downloads/1 非洲雨水追逐之旅.mp4"
        query_text = "视频中，旁白介绍了一头成年大象一天要吃超过多少公斤的植物？"

        print("🎬 开始视频理解...")
        result = await understand_video(video_file, query_text, fps=2)
        print("\n📜 输出结果：\n", result)


    asyncio.run(main())
