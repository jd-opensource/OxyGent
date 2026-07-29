import json
import time
import subprocess
from typing import List, Dict
from oxygent.oxy import FunctionHub

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

bilibili_tools = FunctionHub(name="bilibili_tools")


def _search_bilibili_html(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from bs4 import BeautifulSoup
    import time

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--lang=zh-CN,zh")

    driver = webdriver.Chrome(options=chrome_options)

    def fetch(url, type_flag):
        driver.get(url)
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        results = []

        if type_flag == "video":
            items = soup.select(".bili-video-card")[:max_results]
            for idx, item in enumerate(items, 1):
                title_tag = item.select_one("h3")
                link_tag = item.select_one("a[href]")
                if not (title_tag and link_tag): continue
                title = title_tag.get_text(strip=True)
                url = link_tag["href"]
                url = "https:" + url if url.startswith("//") else url
                results.append({
                    "rank": str(idx), "title": title, "url": url, "type": "video"
                })
            return results

        elif type_flag == "bangumi":
            # ✅ 2025 新版 B 站番剧 DOM
            selectors = [
                ".bangumi-card", ".pgc-item", ".pgc-item-wrapper",
                ".media-card", ".b-subject-item"
            ]
            items = []
            for s in selectors:
                items = soup.select(s)
                if items: break

            for idx, item in enumerate(items[:max_results], 1):
                title_tag = item.select_one("a[title], .bangumi-title, .title")
                if not title_tag: continue
                title = title_tag.get("title") or title_tag.get_text(strip=True)
                url = title_tag.get("href", "")
                url = "https:" + url if url.startswith("//") else url

                # ✅ 只保留番剧/纪录片真实入口
                if not any(x in url for x in ["bangumi", "/ep", "/ss"]):
                    continue

                results.append({
                    "rank": str(idx), "title": title, "url": url, "type": "bangumi"
                })
            return results

    # ✅ 搜视频
    video_results = fetch(f"https://search.bilibili.com/video?keyword={query}", "video")

    # ✅ 搜番剧/纪录片/动画/综艺
    bangumi_results = fetch(f"https://search.bilibili.com/bangumi?keyword={query}", "bangumi")

    driver.quit()

    # ✅ 合并结果，番剧优先
    return bangumi_results + video_results


@bilibili_tools.tool(description="Search Bilibili for videos & bangumi (documentaries, anime).")
def search_bilibili(query: str) -> str:
    results = _search_bilibili_html(query, max_results=10)
    return json.dumps(results, ensure_ascii=False, indent=2)


@bilibili_tools.tool(description="Download normal Bilibili video via yt-dlp.")
def download_bilibili_video(url: str, output_dir: str = "./downloads") -> str:
    """
    普通视频下载函数
    """
    try:
        cmd = [
            "yt-dlp",
            "-o", f"{output_dir}/%(title)s.%(ext)s",
            url
        ]
        subprocess.run(cmd, check=True)
        return json.dumps({"status": "success", "message": f"Video saved to {output_dir}"}, ensure_ascii=False)

    except subprocess.CalledProcessError as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)

import asyncio

if __name__ == "__main__":
    async def main():
        query = "人生一串"
        print("🔍 正在搜索:", query)
        results_json = await search_bilibili(query)  # ✅ 加 await
        print("✅ 搜索结果:\n", results_json)

        results = json.loads(results_json)
        if results:
            first_video = results[0]["url"]
            print(f"\n🎬 开始下载第一个视频: {first_video}")
            #print(await download_bilibili_bangumi(first_video))  # ✅ 这里也加 await
        else:
            print("❌ 未找到视频结果。")

    asyncio.run(main())
