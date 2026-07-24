"""
浏览器自动登录功能

提供自动检测和处理登录表单的功能
"""

import asyncio
import os
import uuid
from datetime import datetime

from pydantic import Field

from .core import _ensure_page, _set_operation_status, _verify_data_ready, mcp
from .utils import _get_domain_from_url

# 域名登录配置字典，包含不同域名对应的选择器配置
LOGIN_DOMAIN_CONFIGS = {
    "ssa.jd.com": {
        "username_selector": "#username",
        "password_selector": "#password",
        "submit_selector": "#formsubmitButton",
    },
    # 可以添加更多域名的配置
    # "example.com": {
    #     "username_selector": "#login-username",
    #     "password_selector": "#login-password",
    #     "submit_selector": "#login-button"
    # }
}


async def _auto_login_with_config(
    page,
    domain=None,
    username=None,
    password=None,
    env_username_key="JD_ERP_USERNAME",
    env_password_key="JD_ERP_PASSWORD",
):
    """
    使用配置自动登录

    参数:
    - page: 页面对象
    - domain: 域名，用于获取配置
    - username: 用户名，如果为None则从环境变量获取
    - password: 密码，如果为None则从环境变量获取
    - env_username_key: 环境变量中用户名的键名
    - env_password_key: 环境变量中密码的键名
    """
    try:
        # 如果未提供用户名或密码，则从环境变量获取
        login_username = username
        login_password = password

        if not login_username:
            login_username = os.getenv("JD_ERP_USERNAME")
        if not login_password:
            login_password = os.getenv(env_password_key)

        if not login_username or not login_password:
            print(
                f"未提供用户名或密码，且未找到环境变量 {env_username_key} 或 {env_password_key}"
            )
            return False

        # 获取域名配置
        domain_config = None
        if domain and domain in LOGIN_DOMAIN_CONFIGS:
            domain_config = LOGIN_DOMAIN_CONFIGS[domain]
            print(f"使用域名 {domain} 的特定配置")

            # 使用特定配置
            try:
                username_selector = domain_config["username_selector"]
                password_selector = domain_config["password_selector"]
                submit_selector = domain_config["submit_selector"]

                # 查找用户名输入框
                username_element = await page.query_selector(username_selector)
                if not username_element:
                    print(f"未找到用户名输入框: {username_selector}")
                    # 如果找不到特定选择器，回退到通用模式
                else:
                    # 清除并输入用户名
                    await asyncio.sleep(1)
                    await username_element.fill("")
                    await username_element.type(login_username, delay=100)

                    # 查找密码输入框
                    password_element = await page.query_selector(password_selector)
                    if not password_element:
                        print(f"未找到密码输入框: {password_selector}")
                        # 如果找不到特定选择器，回退到通用模式
                    else:
                        # 清除并输入密码
                        await asyncio.sleep(1)
                        await password_element.fill("")
                        await password_element.type(login_password, delay=100)

                        # 等待一下，确保输入完成
                        await asyncio.sleep(1)

                        # 查找提交按钮
                        submit_button = await page.query_selector(submit_selector)
                        if not submit_button:
                            print(f"未找到提交按钮: {submit_selector}")
                            # 如果找不到特定选择器，回退到通用模式
                        else:
                            # 点击提交按钮
                            await submit_button.click()
                            # 等待登录完成
                            await asyncio.sleep(3)
                            return True
            except Exception as e:
                print(f"使用特定配置登录失败: {str(e)}")
                # 如果使用特定配置失败，回退到通用模式

        # 尝试不同的登录表单模式
        login_patterns = [
            # 模式1: 标准登录表单
            {
                "username_selector": "input[name='username'], input[name='username'], #username, #username",
                "password_selector": "input[name='password'], input[type='password'], #password",
                "submit_selector": "#formsubmitButton, button[type='submit'], input[type='submit'], .login-btn, #login-btn, button:contains('登录')",
            },
            # 模式2: 京东特定登录表单
            {
                "username_selector": ".itxt[name='username'], .itxt[name='username']",
                "password_selector": ".itxt[name='password'], .itxt[type='password']",
                "submit_selector": "#formsubmitButton, .btn-login, .login-btn",
            },
        ]

        for pattern in login_patterns:
            try:
                # 尝试查找用户名输入框
                username_element = await page.query_selector(
                    pattern["username_selector"]
                )
                if not username_element:
                    continue

                # 清除并输入用户名
                await username_element.fill("")
                await username_element.type(login_username, delay=100)

                # 尝试查找密码输入框
                password_element = await page.query_selector(
                    pattern["password_selector"]
                )
                if not password_element:
                    continue

                # 清除并输入密码
                await password_element.fill("")
                await password_element.type(login_password, delay=100)

                # 等待一下，确保输入完成
                await asyncio.sleep(1)

                # 尝试查找提交按钮
                submit_button = await page.query_selector(pattern["submit_selector"])
                if submit_button:
                    await submit_button.click()
                    # 等待登录完成
                    await asyncio.sleep(3)
                    return True
            except Exception as e:
                print(f"尝试登录模式失败: {str(e)}")
                continue

        return False
    except Exception as e:
        print(f"自动登录失败: {str(e)}")
        return False


async def _auto_login_jd(page):
    """自动登录京东（兼容旧版本，调用_auto_login_with_config）"""
    # 获取当前页面的域名
    current_domain = await _get_domain_from_url(page.url)
    return await _auto_login_with_config(page, domain=current_domain)


async def _detect_2fa_required(page):
    """检测页面是否需要二次认证（如扫码验证）"""
    try:
        # 检查页面是否包含二次认证相关元素
        qr_selectors = [
            "img[src*='qrcode']",
            ".qrcode",
            "#qrcode",
            "canvas.qrcode",
            "div[class*='qr']",
            "div[id*='qr']",
            "img[alt*='扫码']",
            "img[alt*='二维码']",
        ]

        # 检查是否存在二维码元素
        for selector in qr_selectors:
            qr_element = await page.query_selector(selector)
            if qr_element:
                print(f"检测到可能的二维码元素: {selector}")
                return True

        # 检查页面文本中是否包含二次认证相关词语
        content = await page.content()
        auth_keywords = [
            "扫码登录",
            "扫码验证",
            "二次验证",
            "两步验证",
            "双重认证",
            "scan qr code",
            "scan to login",
            "two-factor",
            "2fa",
            "扫描二维码",
            "扫一扫",
            "微信扫码",
            "支付宝扫码",
            "手机验证",
        ]

        for keyword in auth_keywords:
            if keyword.lower() in content.lower():
                print(f"页面内容包含二次认证关键词: {keyword}")
                return True

        return False
    except Exception as e:
        print(f"检查二次认证页面时发生错误: {str(e)}")
        return False


async def _save_login_screenshot(page, prefix="login_page"):
    """保存登录页面截图到缓存目录"""
    try:
        # 创建保存截图的目录
        cache_dir = os.path.join(os.getcwd(), "../", "cache_dir")
        os.makedirs(cache_dir, exist_ok=True)

        # 创建登录截图子目录
        login_dir = os.path.join(cache_dir, "login_screenshots")
        os.makedirs(login_dir, exist_ok=True)

        # 生成唯一的文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"{prefix}_{timestamp}_{unique_id}.png"

        # 完整的保存路径
        save_path = os.path.join(login_dir, filename)

        # 截取截图
        screenshot_bytes = await page.screenshot(full_page=False)

        # 保存截图到文件
        with open(save_path, "wb") as f:
            f.write(screenshot_bytes)

        print(f"登录页面截图已保存到: {save_path}")
        return save_path
    except Exception as e:
        print(f"保存登录页面截图时发生错误: {str(e)}")
        return None


async def _handle_2fa_authentication(page, wait_for_2fa=True):
    """处理二次认证，截屏并等待用户完成认证"""
    try:
        print("检测到需要二次认证，准备截屏...")

        # 创建保存截图的目录
        cache_dir = os.path.join(os.getcwd(), "../", "cache_dir")
        os.makedirs(cache_dir, exist_ok=True)

        # 创建二次认证截图子目录
        auth_dir = os.path.join(cache_dir, "2fa_auth")
        os.makedirs(auth_dir, exist_ok=True)

        # 生成唯一的文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"2fa_auth_{timestamp}_{unique_id}.png"

        # 完整的保存路径
        save_path = os.path.join(auth_dir, filename)

        # 截取截图
        screenshot_bytes = await page.screenshot(full_page=False)

        # 保存截图到文件
        with open(save_path, "wb") as f:
            f.write(screenshot_bytes)

        print(f"二次认证截图已保存到: {save_path}")

        if wait_for_2fa:
            print("等待用户完成二次认证...")
            print(f"请查看截图 {save_path} 并完成扫码认证")

            # 在MCP环境中，我们不能使用input()函数，因为它会阻塞整个进程
            # 而是返回截图路径，让调用者决定如何处理二次认证
            # 等待一段时间，给用户足够的时间查看截图
            await asyncio.sleep(5)

            # 返回结果，包含截图路径和状态信息
            return {
                "status": "pending_2fa",
                "message": "需要二次认证，已保存截图",
                "screenshot_path": save_path,
                "action_required": "请查看截图并完成二次认证，然后继续操作",
            }
        else:
            # 如果不等待二次认证，直接返回结果
            return {
                "status": "success",
                "message": "已处理二次认证请求，但不等待完成",
                "screenshot_path": save_path,
            }
    except Exception as e:
        print(f"处理二次认证时发生错误: {str(e)}")
        return {
            "status": "error",
            "message": f"处理二次认证时发生错误: {str(e)}",
            "error": str(e),
        }


@mcp.tool(description="自动填充账号密码并登录")
async def browser_auto_login(
    url: str = Field(description="要登录的网站URL"),
    username: str = Field(default="", description="用户名，如果为空则从环境变量获取"),
    password: str = Field(default="", description="密码，如果为空则从环境变量获取"),
    wait_after_login: int = Field(default=3, description="登录后等待的时间(秒)"),
    wait_for_2fa: bool = Field(default=True, description="是否等待用户完成二次认证"),
):
    """
    自动填充账号密码并登录，支持自动检测登录表单或使用指定的选择器

    如果未提供用户名和密码，将从环境变量中获取
    如果未提供选择器，将尝试自动检测登录表单元素
    """
    # 检查依赖
    from .core import check_dependencies

    missing_deps = check_dependencies()
    if missing_deps:
        return f"缺少必要的库: {', '.join(missing_deps)}。请使用pip安装: pip install {' '.join(missing_deps)}"

    try:
        await _set_operation_status(True)
        page = await _ensure_page()

        # 导航到登录页面
        if url:
            await page.goto(url, wait_until="load")
            await asyncio.sleep(2)  # 增加等待时间，确保页面完全加载和渲染

        # 保存登录页面截图，无论是否需要二次认证
        login_screenshot_path = await _save_login_screenshot(page, "login_page")

        # 获取登录凭据
        login_username = username
        login_password = password

        # 去除用户名和密码的前后空格
        if login_username and login_username != "#username":
            login_username = login_username.strip()
        if login_password and login_password != "#password":
            login_password = login_password.strip()

        # 如果未提供用户名或密码，则从环境变量获取
        if not login_username:
            login_username = os.getenv("JD_ERP_USERNAME")
        if not login_password:
            login_password = os.getenv("JD_ERP_PASSWORD")

        if not login_username or not login_password:
            await _set_operation_status(False)
            return {
                "status": "error",
                "message": "未提供用户名或密码，且未找到环境变量 JD_ERP_USERNAME 或 JD_ERP_PASSWORD",
                "login_screenshot_path": login_screenshot_path,
            }

        # 获取当前页面的域名
        current_domain = await _get_domain_from_url(page.url)

        # 检查是否有该域名的特定配置
        domain_config = LOGIN_DOMAIN_CONFIGS.get(current_domain)

        # 初始化通用模式标志
        use_generic_mode = domain_config is None
        # 如果有该域名的特定配置，使用特定的选择器
        if domain_config:
            print(f"检测到{current_domain}域名，使用特定选择器")
            # 使用特定的选择器
            username_selector = domain_config["username_selector"]
            password_selector = domain_config["password_selector"]
            submit_selector = domain_config["submit_selector"]

            try:
                # 查找用户名输入框
                username_element = await page.query_selector(username_selector)
                if not username_element:
                    print(f"未找到用户名输入框: {username_selector}")
                    # 如果找不到特定选择器，回退到通用模式
                    use_generic_mode = True
                else:
                    # 清除并输入用户名
                    # 等待一下，确保输入完成
                    await asyncio.sleep(1)
                    await username_element.fill("")

                    await asyncio.sleep(1)
                    await username_element.type(login_username, delay=100)

                    # 查找密码输入框
                    password_element = await page.query_selector(password_selector)
                    if not password_element:
                        print(f"未找到密码输入框: {password_selector}")
                        # 如果找不到特定选择器，回退到通用模式
                        use_generic_mode = True
                    else:
                        # 清除并输入密码
                        # 等待一下，确保输入完成
                        await asyncio.sleep(1)
                        await password_element.fill("")

                        # 等待一下，确保输入完成
                        await asyncio.sleep(1)
                        # 直接输入正确的密码，移除测试密码输入
                        await password_element.type(login_password, delay=100)

                        # 等待一下，确保输入完成
                        await asyncio.sleep(1)

                        # 查找提交按钮
                        submit_button = await page.query_selector(submit_selector)
                        if not submit_button:
                            print(f"未找到提交按钮: {submit_selector}")
                            # 如果找不到特定选择器，回退到通用模式
                            use_generic_mode = True
                        else:
                            # 点击提交按钮
                            await submit_button.click()
                            # 等待登录完成
                            await asyncio.sleep(wait_after_login)

                            # 检查是否需要二次认证
                            needs_2fa = await _detect_2fa_required(page)
                            if needs_2fa:
                                print("检测到需要二次认证")
                                # 处理二次认证
                                auth_result = await _handle_2fa_authentication(
                                    page, wait_for_2fa
                                )

                                await _verify_data_ready()
                                await _set_operation_status(False)

                                # 获取二次认证状态
                                auth_status = auth_result.get("status", "")

                                # 构建返回结果
                                result = {
                                    "url": page.url,
                                    "title": await page.title(),
                                    "domain": current_domain,
                                    "login_username": login_username,
                                    "two_factor_auth": True,
                                    "two_factor_auth_status": auth_status,
                                    "screenshot_path": auth_result.get(
                                        "screenshot_path", ""
                                    ),
                                    "login_screenshot_path": login_screenshot_path,
                                }

                                # 根据二次认证状态设置不同的返回信息
                                if auth_status == "pending_2fa":
                                    result["status"] = "pending_2fa"
                                    result["message"] = "登录成功，但需要完成二次认证"
                                    result["action_required"] = auth_result.get(
                                        "action_required", "请完成二次认证"
                                    )
                                elif auth_status == "success":
                                    result["status"] = "success"
                                    result["message"] = "登录成功，并已处理二次认证"
                                else:
                                    result["status"] = auth_status
                                    result["message"] = auth_result.get(
                                        "message", "二次认证处理状态未知"
                                    )

                                return result
                            else:
                                await _verify_data_ready()
                                await _set_operation_status(False)

                                return {
                                    "status": "success",
                                    "message": "使用特定选择器登录成功",
                                    "url": page.url,
                                    "title": await page.title(),
                                    "domain": current_domain,
                                    "login_username": login_username,
                                    "login_screenshot_path": login_screenshot_path,
                                }
            except Exception as e:
                print(f"使用特定选择器登录失败: {str(e)}")
                # 如果使用特定选择器失败，回退到通用模式
                use_generic_mode = True

        # 只有在需要使用通用模式时才执行下面的代码
        if use_generic_mode:
            print("使用通用模式尝试登录...")
            # 使用自动检测登录表单的方式
            # 尝试不同的登录表单模式
            login_patterns = [
                # 模式1: 标准登录表单
                {
                    "username_selector": "input[name='username'], input[id='username'], #username, .username, [placeholder*='用户名'], [placeholder*='账号'], [placeholder*='邮箱']",
                    "password_selector": "input[name='password'], input[type='password'], #password, .password, [placeholder*='密码']",
                    "submit_selector": "#formsubmitButton, button[type='submit'], input[type='submit'], .login-btn, #login-btn, button:contains('登录'), button:contains('Login'), [aria-label*='login'], [aria-label*='登录']",
                },
                # 模式2: 京东特定登录表单
                {
                    "username_selector": ".itxt[name='username'], .itxt[name='loginname'], .itxt[name='account']",
                    "password_selector": ".itxt[name='password'], .itxt[type='password']",
                    "submit_selector": "#formsubmitButton, .btn-login, .login-btn",
                },
                # 模式3: 通用邮箱登录表单
                {
                    "username_selector": "input[type='email'], input[name='email']",
                    "password_selector": "input[type='password']",
                    "submit_selector": "button[type='submit'], input[type='submit'], .submit-btn, #submit",
                },
                # 模式4: 更宽松的通用表单
                {
                    "username_selector": "input:not([type='password']):not([type='submit']):not([type='checkbox']):not([type='radio'])",
                    "password_selector": "input[type='password']",
                    "submit_selector": "button, input[type='submit'], .btn, [role='button']",
                },
            ]

            for pattern in login_patterns:
                try:
                    # 打印当前尝试的模式
                    print(f"尝试登录模式: {login_patterns.index(pattern) + 1}")

                    # 尝试查找用户名输入框
                    username_element = await page.query_selector(
                        pattern["username_selector"]
                    )
                    if not username_element:
                        print(f"未找到用户名输入框: {pattern['username_selector']}")
                        continue

                    # 清除并输入用户名
                    await username_element.fill("")
                    await username_element.type(login_username, delay=100)

                    # 尝试查找密码输入框
                    password_element = await page.query_selector(
                        pattern["password_selector"]
                    )
                    if not password_element:
                        print(f"未找到密码输入框: {pattern['password_selector']}")
                        continue

                    # 清除并输入密码
                    await password_element.fill("")
                    await password_element.type(login_password, delay=100)

                    # 等待一下，确保输入完成
                    await asyncio.sleep(1)

                    # 尝试查找提交按钮
                    submit_button = await page.query_selector(
                        pattern["submit_selector"]
                    )
                    if not submit_button:
                        print(f"未找到提交按钮: {pattern['submit_selector']}")
                        continue

                    print("找到完整的登录表单，尝试登录...")
                    await submit_button.click()
                    # 等待登录完成
                    await asyncio.sleep(wait_after_login)

                    # 检查是否需要二次认证
                    needs_2fa = await _detect_2fa_required(page)
                    if needs_2fa:
                        print("检测到需要二次认证")
                        # 处理二次认证
                        auth_result = await _handle_2fa_authentication(
                            page, wait_for_2fa
                        )

                        await _verify_data_ready()
                        await _set_operation_status(False)

                        # 获取二次认证状态
                        auth_status = auth_result.get("status", "")

                        # 构建返回结果
                        result = {
                            "url": page.url,
                            "title": await page.title(),
                            "pattern_used": pattern,
                            "two_factor_auth": True,
                            "two_factor_auth_status": auth_status,
                            "screenshot_path": auth_result.get("screenshot_path", ""),
                            "login_screenshot_path": login_screenshot_path,
                        }

                        # 根据二次认证状态设置不同的返回信息
                        if auth_status == "pending_2fa":
                            result["status"] = "pending_2fa"
                            result["message"] = "登录成功，但需要完成二次认证"
                            result["action_required"] = auth_result.get(
                                "action_required", "请完成二次认证"
                            )
                        elif auth_status == "success":
                            result["status"] = "success"
                            result["message"] = "登录成功，并已处理二次认证"
                        else:
                            result["status"] = auth_status
                            result["message"] = auth_result.get(
                                "message", "二次认证处理状态未知"
                            )

                        return result
                    else:
                        await _verify_data_ready()
                        await _set_operation_status(False)

                        return {
                            "status": "success",
                            "message": "登录成功",
                            "url": page.url,
                            "title": await page.title(),
                            "pattern_used": pattern,
                            "login_screenshot_path": login_screenshot_path,
                        }
                except Exception as e:
                    print(f"尝试登录模式失败: {str(e)}")
                    continue

        # 如果执行了通用模式但所有模式都失败，或者没有执行通用模式（特定域名配置失败）
        await _set_operation_status(False)

        # 获取页面HTML结构，帮助调试
        page_content = await page.content()
        form_elements = await page.query_selector_all("form")
        input_elements = await page.query_selector_all("input")

        error_message = "无法自动检测登录表单，请提供具体的选择器"
        if not use_generic_mode:
            error_message = "特定域名配置处理失败，且未启用通用模式"

        return {
            "status": "error",
            "message": error_message,
            "debug_info": {
                "url": page.url,
                "title": await page.title(),
                "forms_count": len(form_elements),
                "inputs_count": len(input_elements),
                "content_length": len(page_content),
                "used_generic_mode": use_generic_mode,
            },
            "login_screenshot_path": login_screenshot_path,
        }
    except Exception as e:
        await _set_operation_status(False)
        return {"status": "error", "message": f"自动登录时发生错误: {str(e)}"}
