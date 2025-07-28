# ========= Copyright 2023-2024 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ========= Copyright 2023-2024 @ CAMEL-AI.org. All Rights Reserved. =========

import json
import os
import re
import logging
import asyncio
import io
from typing import Any, Dict, List, Optional, Tuple, Union
from PIL import Image
from playwright.async_api import BrowserContext, Page, Locator, async_playwright
from camel.agents import ChatAgent
from camel.messages import BaseMessage
from camel.models import ModelFactory
from camel.types import ModelPlatformType
from pydantic import Field

logger = logging.getLogger(__name__)

# Google Maps Specific Actions
GOOGLE_MAPS_ACTIONS_PROMPT = """
1. `click_id(identifier: Union[str, int])`: Click an element with the given ID.
2. `enter_street_view()`: Enter street view mode at the current location. Returns content of visible markers if applicable.
3. `street_view_move_forward()`: Move forward in street view by clicking on the center.
4. `street_view_move_backward()`: Move backward in street view by pressing down arrow key.
5. `street_view_turn_left()`: Turn left in street view (counterclockwise rotation).
6. `street_view_turn_right()`: Turn right in street view (clockwise rotation).
7. `show_historical_dates()`: Show the historical dates for the current street view location.
8. `select_historical_date(date: str)`: Select a specific historical date to view. e.g. July 2010
11. `back()`: Navigate back to the previous page.
12. `stop()`: Stop the action process.
13. `get_url()`: Get the current URL.
14. `find_text_on_page(search_text: str)`: Find text on the page.
16. `click_blank_area()`: Click a blank area to unfocus.
17. `click_marker(index: int)`: After enter_street_view, Click on a map marker by its visible index.
19. `flip_view()`: Flip street view perspective 180 degrees (executes two consecutive rotations)
20. `move_left()`: Move left by temporarily rotating CCW 90°, advancing, then restoring direction
21. `move_right()`: Move right by temporarily rotating CW 90°, advancing, then restoring direction
"""

GOOGLE_MAPS_ACTIONS = [
    "click_id",
    "enter_street_view",
    "street_view_move_forward",
    "street_view_move_backward",
    "street_view_turn_left",
    "street_view_turn_right",
    "show_historical_dates",
    "select_historical_date",
    "back",
    "stop",
    "find_text_on_page",
    "click_blank_area",
    "click_marker",
    "flip_view",
    "move_left",
    "move_right"
]


def _parse_json_output(text: str) -> Dict[str, Any]:
    """Extract JSON output from a string"""
    # Try to extract from Markdown code block
    markdown_pattern = r'```(?:json)?\s*(.*?)\s*```'
    markdown_match = re.search(markdown_pattern, text, re.DOTALL)
    if markdown_match:
        text = markdown_match.group(1).strip()

    # Try to extract from triple quotes
    triple_quotes_pattern = r'"""(?:json)?\s*(.*?)\s*"""'
    triple_quotes_match = re.search(triple_quotes_pattern, text, re.DOTALL)
    if triple_quotes_match:
        text = triple_quotes_match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parsing failed: {e}. Attempting to fix string...")
        # Remove trailing incomplete JSON
        text = re.sub(r',\s*[}\]][^\]}]*$', '', text)
        # Replace possible incorrect key-value pairs
        text = re.sub(r'(\w+):', r'"\1":', text)
        try:
            return json.loads(text)
        except json.JSONDecodeError as e2:
            logger.error(f"Failed to fix JSON: {e2}")
            return {"error": "Failed to parse JSON output"}


class GoogleMapsBrowser:
    def __init__(self, headless: bool = True, cache_dir: Optional[str] = None):
        self.headless = headless
        self._playwright = None
        self._browser = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.page_history: List[str] = []
        self.cache_dir = cache_dir or "/tmp/google_maps_cache"
        os.makedirs(self.cache_dir, exist_ok=True)
        self.visible_markers_count = 0
        self.start_url = None

    async def init(self):
        """Asynchronously initialize the browser"""
        if self.page and not self.page.is_closed():
            await self.page.close()

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        self.context = await self._browser.new_context(accept_downloads=True)
        self.page = await self.context.new_page()
        await self.page.set_viewport_size({"width": 1280, "height": 720})

    async def wait_for_load(self, timeout: int = 5):
        """Asynchronously wait for the page to load"""
        if not self.page:
            return

        try:
            await self.page.wait_for_load_state("domcontentloaded", timeout=timeout * 1000)
            await self.page.wait_for_load_state("networkidle", timeout=timeout * 1000)
            await asyncio.sleep(0.5)  # Additional buffer time
        except Exception as e:
            logger.warning(f"Timeout waiting for page load: {e}")

    async def visit_page(self, url: str):
        """Asynchronously visit a specified URL"""
        if not self.page:
            return

        await self.page.goto(url, timeout=60000)
        await self.wait_for_load()
        self.page_url = url
        self.page_history.append(url)

    async def click_id(self, identifier: Union[str, int]) -> bool:
        """Asynchronously click an element by ID or index"""
        if not self.page:
            return False

        try:
            if isinstance(identifier, int):
                # Select by index
                elements = await self.page.query_selector_all('*')
                if identifier < len(elements):
                    await elements[identifier].scroll_into_view_if_needed()
                    await elements[identifier].click(timeout=3000)
                    await self.wait_for_load()
                    return True
                return False
            else:
                # Select by ID
                locator = self.page.locator(f"#{identifier}")
                if await locator.count() > 0:
                    await locator.scroll_into_view_if_needed()
                    await locator.first.click(timeout=3000)
                    await self.wait_for_load()
                    return True
                return False
        except Exception as e:
            logger.error(f"Error clicking element: {e}")
            return False

    async def enter_street_view(self) -> Union[bool, List[Dict]]:
        """Asynchronously enter street view mode"""
        if not self.page:
            return False

        try:
            # Try to find and click the "Street View" or equivalent button
            street_view_btns = [
                "button[aria-label='Street View']",
                "button[aria-label='街景']",
                "button[aria-label='Street View and 360° photos']",
                "button[aria-label='街景和 360 度全景照']"
            ]

            found = False
            for btn_selector in street_view_btns:
                btn = await self.page.query_selector(btn_selector)
                if btn and await btn.is_visible():
                    await btn.click(timeout=5000)
                    await self.wait_for_load()
                    found = True
                    break

            if found:
                street_view_button = self.page.locator("button[class='yra0jd Hk4XGb']")
                await street_view_button.click(timeout=5000)
                return True

            # Check for markers
            markers = await self.page.query_selector_all('.hfpxzc')
            markers_info = []

            for idx, marker in enumerate(markers):
                if await marker.is_visible():
                    # Get marker title
                    title = await marker.get_attribute('aria-label') or f"Marker {idx}"
                    markers_info.append({
                        "index": idx,
                        "title": title,
                        "element": marker
                    })

            # Return marker information for selection
            return markers_info

        except Exception as e:
            logger.error(f"Error entering street view: {e}")
            return False

    async def click_marker(self, index: int) -> bool:
        """Asynchronously click a map marker by index"""
        if not self.page:
            return False

        try:
            markers = await self.page.query_selector_all('.hfpxzc')
            visible_markers = [m for m in markers if await m.is_visible()]

            if not (0 <= index < len(visible_markers)):
                logger.error(f"Invalid index {index}, there are {len(visible_markers)} visible markers")
                return False

            # Click the marker
            await visible_markers[index].scroll_into_view_if_needed()
            await visible_markers[index].click(timeout=5000)
            await self.wait_for_load()

            # Try to enter street view from the new panel
            return await self.enter_street_view() is True

        except Exception as e:
            logger.error(f"Error clicking marker: {e}")
            return False

    async def street_view_move_forward(self) -> bool:
        """Asynchronously move forward in street view (click center of screen)"""
        if not self.page:
            return False

        try:
            # Get viewport dimensions
            viewport = await self.page.evaluate("() => ({width: window.innerWidth, height: window.innerHeight})")
            center_x = viewport["width"] // 2
            center_y = viewport["height"] // 2

            # Click center of screen
            await self.page.mouse.click(center_x, center_y)
            await asyncio.sleep(2)  # Wait for movement to complete
            return True
        except Exception as e:
            logger.error(f"Failed to move forward: {e}")
            return False

    async def street_view_move_backward(self) -> bool:
        """Asynchronously move backward in street view (press down arrow key)"""
        if not self.page:
            return False

        try:
            # Simulate pressing down arrow key
            await self.page.keyboard.press("ArrowDown")
            await asyncio.sleep(1)  # Wait for movement to complete
            return True
        except Exception as e:
            logger.error(f"Failed to move backward: {e}")
            return False

    async def street_view_turn_left(self) -> bool:
        """Asynchronously turn left in street view (counterclockwise rotation)"""
        if not self.page:
            return False

        try:
            # Locate counterclockwise rotation button
            counterclockwise_btn = await self.page.query_selector("button[aria-label='逆时针旋转视图']")
            if counterclockwise_btn and await counterclockwise_btn.is_visible():
                await counterclockwise_btn.click(timeout=3000)
                await asyncio.sleep(0.5)
                return True

            logger.error("Counterclockwise rotation button not found")
            return False
        except Exception as e:
            logger.error(f"Failed to turn left: {e}")
            return False

    async def street_view_turn_right(self) -> bool:
        """Asynchronously turn right in street view (clockwise rotation)"""
        if not self.page:
            return False

        try:
            # Locate clockwise rotation button
            clockwise_btn = await self.page.query_selector("button[aria-label='顺时针旋转视图']")
            if clockwise_btn and await clockwise_btn.is_visible():
                await clockwise_btn.click(timeout=3000)
                await asyncio.sleep(0.5)
                return True

            logger.error("Clockwise rotation button not found")
            return False
        except Exception as e:
            logger.error(f"Failed to turn right: {e}")
            return False

    async def show_historical_dates(self) -> Union[bool, list]:
        """Asynchronously show historical dates panel"""
        if not self.page:
            return False

        try:
            # Try to find and click the "More dates" button
            date_button = await self.page.query_selector("button.LQDejd")
            if not date_button:
                date_button = await self.page.query_selector("text='查看更多日期'")

            if date_button and await date_button.is_visible():
                await date_button.click(timeout=5000)
                await asyncio.sleep(1)  # Wait for panel to load
                # Find date buttons
                date_buttons = await self.page.query_selector_all("button[class='aLPB6c kaqDpe']")
                aria_labels = []
                for button in date_buttons:
                    aria_label = await button.get_attribute('aria-label')
                    if aria_label:
                        aria_labels.append(aria_label)
                return aria_labels
            return False
        except Exception as e:
            logger.error(f"Failed to show historical dates: {e}")
            return False

    async def select_historical_date(self, date_str: str) -> bool:
        """Asynchronously select a specific historical date"""
        if not self.page:
            return False

        try:
            # Ensure date panel is open
            if not await self.page.query_selector("button[class='aLPB6c kaqDpe']"):
                await self.show_historical_dates()

            # Find date button
            date_button = await self.page.query_selector(f"button[aria-label='{date_str}']")

            # Support more date formats
            if not date_button:
                date_button = await self.page.query_selector(f":text-matches('^{date_str}', 'i')")

            if date_button and await date_button.is_visible():
                await date_button.scroll_into_view_if_needed()
                await date_button.click(timeout=5000)
                await self.wait_for_load()
                await asyncio.sleep(2)  # Wait for street view image to load
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to select historical date: {e}")
            return False

    async def flip_view(self) -> bool:
        """Asynchronously flip street view perspective 180 degrees"""
        if not self.page:
            return False

        try:
            # Since each rotation is 90 degrees, execute two rotations for 180 degrees flip
            success1 = await self.street_view_turn_right()
            await asyncio.sleep(0.5)
            success2 = await self.street_view_turn_right()
            return success1 and success2
        except Exception as e:
            logger.error(f"Failed to flip view: {e}")
            return False

    async def move_left(self) -> bool:
        """Asynchronously move left: rotate left 90 degrees, move forward, then restore direction"""
        if not self.page:
            return False

        try:
            # Rotate left 90 degrees
            if not await self.street_view_turn_left():
                return False

            # Wait for rotation animation to complete
            await asyncio.sleep(1)

            # Move forward
            if not await self.street_view_move_forward():
                return False

            # Wait for movement to complete
            await asyncio.sleep(1)

            # Rotate right 90 degrees to restore original direction
            return await self.street_view_turn_right()
        except Exception as e:
            logger.error(f"Failed to move left: {e}")
            return False

    async def move_right(self) -> bool:
        """Asynchronously move right: rotate right 90 degrees, move forward, then restore direction"""
        if not self.page:
            return False

        try:
            # Rotate right 90 degrees
            if not await self.street_view_turn_right():
                return False

            # Wait for rotation animation to complete
            await asyncio.sleep(1)

            # Move forward
            if not await self.street_view_move_forward():
                return False

            # Wait for movement to complete
            await asyncio.sleep(1)

            # Rotate left 90 degrees to restore original direction
            return await self.street_view_turn_left()
        except Exception as e:
            logger.error(f"Failed to move right: {e}")
            return False

    async def scroll_up(self) -> bool:
        """Asynchronously scroll up the page"""
        if not self.page:
            return False

        try:
            await self.page.keyboard.press("PageUp")
            await asyncio.sleep(0.5)
            return True
        except Exception as e:
            logger.error(f"Failed to scroll up: {e}")
            return False

    async def scroll_down(self) -> bool:
        """Asynchronously scroll down the page"""
        if not self.page:
            return False

        try:
            await self.page.keyboard.press("PageDown")
            await asyncio.sleep(0.5)
            return True
        except Exception as e:
            logger.error(f"Failed to scroll down: {e}")
            return False

    async def back(self) -> bool:
        """Asynchronously navigate back to the previous page"""
        if not self.page:
            return False

        try:
            await self.page.go_back()
            await self.wait_for_load()
            return True
        except Exception as e:
            logger.error(f"Failed to go back: {e}")
            return False

    async def stop(self) -> bool:
        """Stop the operation"""
        return True

    async def get_url(self) -> str:
        """Asynchronously get the current URL"""
        return self.page.url if self.page else ""

    async def find_text_on_page(self, search_text: str) -> bool:
        """Asynchronously find text on the page"""
        if not self.page:
            return False

        try:
            await self.page.keyboard.press("Control+F")
            await self.page.keyboard.type(search_text)
            await asyncio.sleep(1)
            return True
        except Exception as e:
            logger.error(f"Failed to find text: {e}")
            return False

    async def click_blank_area(self) -> bool:
        """Asynchronously click on a blank area"""
        if not self.page:
            return False

        try:
            await self.page.mouse.click(5, 5)  # Small offset from top-left corner
            await asyncio.sleep(0.5)
            return True
        except Exception as e:
            logger.error(f"Failed to click blank area: {e}")
            return False

    async def close(self):
        """Asynchronously close the browser"""
        try:
            if self.page and not self.page.is_closed():
                await self.page.close()
            if self.context:
                await self.context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.error(f"Error closing browser: {e}")


class GoogleMapsAgent:
    def __init__(self, headless: bool = True, cache_dir: Optional[str] = None):
        self.browser = GoogleMapsBrowser(headless=headless, cache_dir=cache_dir)
        self.history: List[Dict] = []
        self.model = self._initialize_model()

    def _initialize_model(self):
        """Initialize the AI model"""
        web_agent_model = ModelFactory.create(
            model_platform=ModelPlatformType.OPENAI,
            model_type=os.getenv('GPT_4O'),
            api_key=os.getenv('OPEN_AI_KEY'),
            url=os.getenv('OPEN_AI_URL'),
        )
        system_prompt = """
                You are a specialized Google Maps agent that helps users navigate and explore locations.
                You have access to Google Maps browser tools to complete tasks.
                When multiple map markers are visible, select the most appropriate one based on context.
                """
        return ChatAgent(
            system_message=system_prompt,
            model=web_agent_model,
            output_language='en',
        )

    async def observe(self, task_prompt: str) -> Tuple[str, str, str]:
        """Asynchronously observe the current page state and decide next action"""
        if not self.browser.page:
            return "", "", "stop"

        screenshot = await self.browser.page.screenshot()
        img = Image.open(io.BytesIO(screenshot))
        history_text = "\n".join([
            f"Step {step['step']}: {step['observation']} -> {step['action_code']} ({'success:' + step['result_info'] if step.get('success') else 'failure'})"
            for step in self.history
        ])

        prompt = f"""You are a specialized Google Maps agent. Need to solve task. Your task is: {task_prompt}

Available actions:
{GOOGLE_MAPS_ACTIONS_PROMPT}

Action history:
{history_text}

Based on the current state of Google Maps, decide the next action to take.

IMPORTANT OPERATION SEQUENCE:
1. ACCESS STREET VIEW:
    ◦ Use `enter_street_view()`
    ◦ If multiple markers:
        a) Choose highest-match marker via `click_marker(index)`
        b) Upon entry: STATICALLY validate target
        c) IF TARGET MISMATCH: 
            ▪︎ IMMEDIATELY execute `back()` ！！！
            ▪︎ Select next marker via `click_marker(next_index)`
        d) ONLY ON MATCH: Proceed to step 2

2. VIEW LOCKING PHASE (ALL ROTATIONS MUST COMPLETE HERE):
   • MANDATORY ORIENTATION SCAN:
        ▪ Full panorama scan: `street_view_turn_left()×4 → street_view_turn_right()×4`
        ▪ Vertical check: `flip_view()×2`
        ▪ Target must occupy center 50% of viewport
   • DISTANCE LOCK (PREPARE FOR DATE SEARCH):
        ▪ Adjust to optimal distance: `move_forward()`/`move_backward()` 
        ▪ Final horizontal centering: `move_left()`/`move_right()`
        ▪ ACTIVATE VIEW LOCK: No more rotations/flips after this point

3. HISTORICAL DATE MATCHING (CRITICAL PHASE):
   • INIT CHECK: `show_historical_dates()`
   • DATE CALIBRATION LOOP (if date mismatch):
        ▪ Execute PRECISION MOVEMENT:
            move_left(), move_forward() or move_right()
        ▪ RECHECK dates after EACH move sequence
        ▪ If date found mid-sequence: BREAK loop immediately
   • ON DATE MATCH:
        ▪ Verify target remains centered/large
        ▪ THEN `select_historical_date(exact_date)`

4. FINAL VALIDATION:
   ▪︎ Confirm date EXACTLY matches requirement
   ▪︎ Ensure target fills >50% viewport

DATE MATCH PRIORITY RULES:
🔷 DATE ACCURACY OVER MOVEMENT: 
    • If date matches but view imperfect → STILL VALID
    • If date mismatch → CONTINUE calibration loop 
🔷 MOVEMENT CONSTRAINTS DURING DATE SEARCH:
    • MAX 2 rotations per rescan
    • NO view flipping during date calibration

TERMINATION CONDITIONS:
✅ SUCCESS: {{"action_code": "final_answer", "answer": ""}}
❌ FAILURE: Only if ALL markers exhausted AND date unavailable


OUTPUT MECHANISM: {{"observation": "...", "reasoning": "...", "action_code": "func"}}
Examples:
1. {{"observation": "Marker2: Correct building", "reasoning": "Init rotation scan to establish baseline", "action_code": "street_view_turn_left()"}}
2. {{"observation": "2024-10-15 available, need 2025-07-22", "reasoning": "Date mismatch! Begin calibration ()", "action_code": "move_forward()"}}
3. {{"observation": "Found 2025-07-22 but building clipped", "reasoning": "DATE MATCHED. Final distance polish", "action_code": "move_backward()"}}
4. {{"observation": "Exact date and optimal view confirmed", "action_code": "final_answer", "answer": "Date:2025-07-22|Result: response"}}
"""

        message = BaseMessage.make_user_message(
            role_name='user',
            content=prompt,
            image_list=[img]
        )

        resp = self.model.step(message)
        content = resp.msgs[0].content

        try:
            resp_dict = _parse_json_output(content)
            print(resp_dict)
            if resp_dict.get('action_code', '').lower() == 'final_answer':
                return "", resp_dict.get("answer", ""), resp_dict.get("action_code", "").strip()
            if isinstance(resp_dict, dict):
                observation = resp_dict.get("observation", "")
                reasoning = resp_dict.get("reasoning", "")
                action_code = resp_dict.get("action_code", "").strip()
                return observation, reasoning, action_code
            return "", "", ""
        except Exception as e:
            logger.error(f"Error parsing observation result: {e}")
            return "", "", ""

    async def act(self, action_code: str) -> Tuple[bool, str]:
        """Asynchronously execute the specified action"""
        action_code = action_code.strip()

        # Special stop cases
        if action_code.lower() in ["stop", "done", "exit"]:
            return True, "Task completed"

        # Process action invocation
        try:
            # Match function call pattern
            match = re.match(r'(\w+)\(([^)]*)\)', action_code)
            if match:
                func_name = match.group(1).strip()
                args_str = match.group(2).strip()

                # Handle arguments specially
                if args_str:
                    # Try to parse numeric argument
                    if args_str.isdigit():
                        arg_value = int(args_str)
                    else:
                        # Try to extract string argument
                        str_match = re.match(r'[\'"]([^\'"]*)[\'"]', args_str)
                        if str_match:
                            arg_value = str_match.group(1)
                        else:
                            # Try numeric argument
                            try:
                                arg_value = int(args_str)
                            except ValueError:
                                arg_value = args_str
                else:
                    arg_value = None
            else:
                func_name = action_code
                arg_value = None

            logger.info(f"Executing action: {action_code}")

            # Check if valid action
            if func_name not in GOOGLE_MAPS_ACTIONS:
                return False, f"Invalid action: {func_name}"

            # Execute based on action type
            if arg_value is not None:
                if func_name == "click_id":
                    result = await self.browser.click_id(arg_value)
                    return result, f"Clicked ID: {arg_value}"
                elif func_name == "select_historical_date":
                    result = await self.browser.select_historical_date(arg_value)
                    return result, f"Selected historical date: {arg_value}"
                elif func_name == "find_text_on_page":
                    result = await self.browser.find_text_on_page(arg_value)
                    return result, f"Searched text: {arg_value}"
                elif func_name == "visit_page":
                    await self.browser.visit_page(arg_value)
                    return True, f"Visited page: {arg_value}"
                elif func_name == "click_marker":
                    if isinstance(arg_value, int):
                        result = await self.browser.click_marker(arg_value)
                        return result, f"Clicked marker #{arg_value}"
                    else:
                        return False, f"Invalid argument for click_marker: {arg_value}"
                else:
                    return False, f"Action {func_name} does not take arguments"
            else:
                # Argument-less actions
                if func_name == "enter_street_view":
                    result = await self.browser.enter_street_view()
                    if isinstance(result, list):
                        return True, f"Found {result} visible markers"
                    else:
                        return result, "Entered street view" if result else "Failed to enter street view"
                elif func_name == 'back':
                    await self.browser.visit_page(self.start_url)
                    return True, f"Executed action: {func_name}:{True}"
                else:
                    action_method = getattr(self.browser, func_name)
                    result = await action_method()
                    if result is False:
                        return False, f"Executed action: {func_name}"
                    return True, f"Executed action: {func_name}:{result}"

        except Exception as e:
            logger.error(f"Error executing action: {e}")
            return False, str(e)

    async def run_task(self, task_prompt: str, start_url: str) -> str:
        """Asynchronously run the specified task"""
        self.start_url = start_url
        await self.browser.init()
        await self.browser.visit_page(self.start_url)

        MAX_STEPS = 15
        for step in range(MAX_STEPS):
            observation, reasoning, action_code = await self.observe(task_prompt)
            if action_code == 'final_answer':
                return reasoning

            # Record history
            step_info = {
                "step": step,
                "observation": observation,
                "reasoning": reasoning,
                "action_code": action_code
            }

            # Special stop cases
            if action_code.lower() in ["stop", "exit", "done"]:
                step_info["status"] = "stopped"
                self.history.append(step_info)
                break

            # Execute action
            success, result_info = await self.act(action_code)
            step_info.update({
                "success": success,
                "result_info": result_info
            })
            self.history.append(step_info)

            if not success:
                logger.warning(f"Step {step} failed: {action_code} - {result_info}")

            # Check if task is complete
            if "stop" in result_info.lower() or "done" in result_info.lower():
                break

        return await self._generate_final_answer(task_prompt)

    async def _generate_final_answer(self, task_prompt: str) -> str:
        """Generate the final answer"""
        history_text = "\n".join([
            f"Step {step['step']}: {step['observation']} -> {step['action_code']} ({'success' if step.get('success') else 'failure'})"
            for step in self.history
        ])

        prompt = f"""
        You have completed the Google Maps task: {task_prompt}

        Action history:
        {history_text}

        Based on this history, provide the final answer to the task.

        Important:
        - If the task requires a specific date, include that date in the answer
        - If the task requires geographic information, include specific details
        - Final answer should be concise and directly answer the user's question
        """

        message = BaseMessage.make_user_message(
            role_name='user',
            content=prompt
        )

        try:
            resp = self.model.step(message)
            return resp.msgs[0].content
        except Exception as e:
            logger.error(f"Error generating final answer: {e}")
            return "Failed to complete the task"

    async def close(self):
        """Asynchronously close the agent"""
        await self.browser.close()


from oxygent import oxy

google_map = oxy.FunctionHub(name="google_map_tool", timeout=900)


@google_map.tool(description="""
    Executes complex Google Maps exploration tasks using browser automation

    This specialized agent can:
    - Navigate street view timelines
    - Find historical imagery
    - Interact with map markers
    - Extract temporal information from visible content

    Task capabilities:
    - Historical date discovery ("What date was this building constructed?")
    - Street view navigation ("Find the store visible in 2012 street view")
    - Visual content recognition ("What brand is the billboard shown in May 2015?")
    - Location-based fact verification ("Was this park present in 2010 imagery?")

    Best used for tasks requiring:
    - Time-based exploration of locations
    - Analysis of dated street view content
    - Historical verification of visible features

    Returns detailed task results or structured data found during exploration
    """)
async def run_google_maps_task_api(
        task_prompt: str = Field(description="Detailed description of the Google Maps task to execute",
                                 examples=[
                                     "Find the release date of the smartphone visible in June 2014 street view at Beijing"]),
        start_url: str = Field(description="Google Maps URL to start the exploration from"),
) -> str:
    agent = GoogleMapsAgent(headless=False)
    result = await agent.run_task(task_prompt, start_url)
    await agent.close()
    return result


# Example usage
async def main():
    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Example task
    task = "Google Street View’s June 2014 imagery for the New Jersey side of the Lincoln Tunnel shows an ad for a smartphone above each of the tunnel entrances. What date was this phone released? Use the MM/DD/YYYY format."
    url = "https://www.google.com/maps/search/the+New+Jersey+side+of+the+Lincoln+Tunnel/@40.7655969,-74.0223049,6629m/data=!3m1!1e3?entry=ttu&g_ep=EgoyMDI1MDcxMy4wIKXMDSoASAFQAw%3D%3D"

    print(f"Executing task: {task}")
    result = await run_google_maps_task_api(
        task_prompt=task,
        start_url=url,
        # headless=False  # Set to True for server environments
    )
    print("\nTask result:")
    print(result)


if __name__ == "__main__":
    # Language set to Chinese
    from dotenv import load_dotenv
    from pathlib import Path
    env_path = Path('../examples/gaia/') / '.env'
    load_dotenv(dotenv_path=env_path, verbose=True)
    print(asyncio.run(main()))
