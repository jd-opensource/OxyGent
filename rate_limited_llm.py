"""
Rate-limited HttpLLM implementation for handling API rate limits more gracefully
"""

import asyncio
import time
from oxygent.oxy.llms.http_llm import HttpLLM
from oxygent.schemas import OxyRequest, OxyResponse, OxyState


class RateLimitedHttpLLM(HttpLLM):
    """HttpLLM with enhanced rate limiting and backoff strategies."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        """Execute with intelligent rate limiting and exponential backoff."""
        
        # 使用类属性而不是实例属性
        if not hasattr(self.__class__, '_last_request_time'):
            self.__class__._last_request_time = 0
            self.__class__._current_backoff = 1.0
        
        min_interval = 5.0  # 最小请求间隔 5 秒
        max_backoff = 60.0  # 最大退避时间
        backoff_factor = 2.0  # 退避因子
        
        # 确保最小请求间隔
        current_time = time.time()
        time_since_last = current_time - self.__class__._last_request_time
        if time_since_last < min_interval:
            wait_time = min_interval - time_since_last
            print(f"🕐 Rate limiting: waiting {wait_time:.1f}s before next request")
            await asyncio.sleep(wait_time)
        
        max_retries = 6  # 增加重试次数
        for attempt in range(max_retries):
            try:
                self.__class__._last_request_time = time.time()
                response = await super()._execute(oxy_request)
                # 成功时重置退避时间
                self.__class__._current_backoff = 1.0
                return response
                
            except Exception as e:
                error_str = str(e).lower()
                
                # 检查是否是 429 错误
                if "429" in error_str or "too many requests" in error_str:
                    if attempt < max_retries - 1:
                        # 指数退避
                        wait_time = min(self.__class__._current_backoff, max_backoff)
                        print(f"⚠️  API rate limit hit (attempt {attempt + 1}/{max_retries}), backing off for {wait_time:.1f}s")
                        await asyncio.sleep(wait_time)
                        self.__class__._current_backoff *= backoff_factor
                        continue
                    else:
                        # 最后一次尝试失败，返回友好错误
                        return OxyResponse(
                            state=OxyState.COMPLETED,
                            output="API 请求频率过高，请稍后再试。系统正在处理您的请求，请耐心等待。"
                        )
                
                # 其他错误直接抛出
                elif attempt == max_retries - 1:
                    return OxyResponse(
                        state=OxyState.FAILED,
                        output=f"请求失败: {str(e)}"
                    )
                else:
                    # 非 429 错误也稍微等待
                    await asyncio.sleep(1.0)
                    continue
        
        return OxyResponse(
            state=OxyState.FAILED,
            output="多次重试后仍然失败，请检查网络连接或稍后再试。"
        )
