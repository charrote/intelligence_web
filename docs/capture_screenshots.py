#!/usr/bin/env python3
"""
Intelligence Web 系统截图工具
使用 Playwright 截取所有功能页面
"""

import asyncio
import os
from playwright.async_api import async_playwright

SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

BASE_URL = "http://localhost:9999/portal"

PAGES = [
    ("login", "login.html", "登录页面"),
    ("shell", "shell.html", "主框架页面"),
    ("index", "index.html", "情报列表页"),
    ("dashboard", "dashboard.html", "数据看板"),
    ("projects", "projects.html", "采集项目"),
    ("datasources", "datasources.html", "数据源管理"),
    ("target_types", "target_types.html", "目标类型"),
    ("analyst", "analyst.html", "AI 分析师"),
    ("users", "users.html", "用户管理"),
    ("roles", "roles.html", "角色管理"),
    ("import", "import.html", "批量导入"),
    ("audit", "audit.html", "操作日志"),
    ("notifications", "notifications.html", "通知中心"),
    ("settings", "settings.html", "系统设置"),
]


async def capture_screenshots():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()

        for screenshot_name, page_path, description in PAGES:
            url = f"{BASE_URL}/{page_path}"
            print(f"正在截图: {description} -> {screenshot_name}.png")
            try:
                await page.goto(url, wait_until="networkidle", timeout=15000)
                # Wait for content to load
                await page.wait_for_timeout(1000)

                screenshot_path = os.path.join(SCREENSHOT_DIR, f"{screenshot_name}.png")
                await page.screenshot(
                    path=screenshot_path,
                    full_page=True,
                )
                print(f"  ✓ 已保存: {screenshot_path}")
            except Exception as e:
                print(f"  ✗ 失败: {e}")
                # Try a quick screenshot even if networkidle fails
                try:
                    screenshot_path = os.path.join(SCREENSHOT_DIR, f"{screenshot_name}.png")
                    await page.screenshot(
                        path=screenshot_path,
                        full_page=True,
                    )
                    print(f"  ✓ 已保存（超时）: {screenshot_path}")
                except Exception as e2:
                    print(f"  ✗ 截图失败: {e2}")

        await browser.close()
        print("所有截图完成！")


if __name__ == "__main__":
    asyncio.run(capture_screenshots())