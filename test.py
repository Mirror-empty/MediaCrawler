from playwright.async_api import async_playwright, Page
import asyncio
import json
from media_platform.kuaishou.graphql import KuaiShouGraphQL


async def fetch_graphql_data():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://www.xiaohongshu.com")
        # 定义Fetch API请求
        uri = 'https://www.xiaohongshu.com/user/profile/59d8cb33de5fb4696bf17217'
        while True:
            # 使用page.evaluate在页面上下文中执行Fetch请求
            response_json = await page.evaluate(
                """ ([uri]) => {
    return (async () => {
      const response = await fetch(uri);
      return response.ok ? await response.json() : null;
    })();
  }""",
                [uri]
            )
            asyncio.sleep(100)
            print(response_json)
        data = response_json.josn()
        await browser.close()


# 运行异步函数

asyncio.run(fetch_graphql_data())
