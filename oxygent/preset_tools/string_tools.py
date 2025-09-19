import re
import json
import asyncio
from pydantic import Field
from oxygent.oxy import FunctionHub

string_tools = FunctionHub(name="string_tools")


@string_tools.tool(
    description="Extract email addresses from text"
)
async def extract_emails(
        text: str = Field(description="Text to extract email addresses from")
) -> str:
    """
    从文本中提取邮箱地址
    """
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, text)
    return json.dumps(list(set(emails)), ensure_ascii=False)


@string_tools.tool(
    description="Extract URLs from text"
)
async def extract_urls(
        text: str = Field(description="Text to extract URLs from")
) -> str:
    """
    从文本中提取URL
    """
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    urls = re.findall(url_pattern, text)
    return json.dumps(list(set(urls)), ensure_ascii=False)


@string_tools.tool(
    description="Validate if a string is a valid email address"
)
async def validate_email(
        email: str = Field(description="Email address to validate")
) -> str:
    """
    验证邮箱地址格式
    """
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    is_valid = bool(re.match(email_pattern, email))
    return json.dumps({"email": email, "is_valid": is_valid}, ensure_ascii=False)


# 异步主函数
async def main():
    # 测试文本数据
    test_text = """
    这是一些包含邮箱和URL的示例文本。
    联系我们：support@example.com 或者 visit our website at https://www.example.com
    更多信息请访问 http://info.example.org 或发送邮件到 info@example.org
    无效的邮箱: invalid.email@ 或 missing@domain
    另一个有效的邮箱: user.name+tag@domain.co.uk
    """

    print("=== String Tools 测试示例 ===\n")

    # 测试邮箱提取功能
    print("1. 提取邮箱地址:")
    emails_result = await extract_emails(text=test_text)
    print(f"   输入文本: {test_text[:50]}...")
    print(f"   提取结果: {emails_result}\n")

    # 测试URL提取功能
    print("2. 提取URL:")
    urls_result = await extract_urls(text=test_text)
    print(f"   输入文本: {test_text[:50]}...")
    print(f"   提取结果: {urls_result}\n")

    # 测试邮箱验证功能
    print("3. 邮箱地址验证:")
    test_emails = [
        "support@example.com",
        "user.name+tag@domain.co.uk",
        "invalid.email@",
        "missing@domain",
        "valid@example.org"
    ]

    for email in test_emails:
        validation_result = await validate_email(email=email)
        print(f"   {email}: {validation_result}")


if __name__ == "__main__":
    # 使用 asyncio.run() 来运行异步主函数
    asyncio.run(main())
