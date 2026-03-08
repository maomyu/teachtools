#!/usr/bin/env python3
"""
调试完形填空页面的词汇高亮位置问题
"""
from playwright.sync_api import sync_playwright
import json

def debug_highlight():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        page.on('console', lambda msg: print(f'[Console] {msg.type}: {msg.text}'))

        # 1. 导航到完形列表页
        print("1. 导航到完形列表页...")
        page.goto('http://localhost:5157/cloze')
        page.wait_for_load_state('networkidle')
        page.wait_for_selector('.ant-table-row', timeout=10000)
        page.wait_for_timeout(2000)

        # 2. 点击第一行打开抽屉
        print("\n2. 点击表格第一行打开抽屉...")
        rows = page.locator('.ant-table-row').all()
        print(f"   找到 {len(rows)} 行")

        if rows:
            rows[0].click()
            page.wait_for_timeout(2000)
            page.screenshot(path='/tmp/cloze_drawer_open.png', full_page=True)
            print("   抽屉已打开，截图: /tmp/cloze_drawer_open.png")

        # 3. 获取 API 数据
        print("\n3. 获取 API 数据...")
        cloze_data = page.request.get('http://localhost:8000/api/cloze/1').json()
        vocabulary = cloze_data.get('vocabulary', [])
        print(f"   API 返回 {len(vocabulary)} 个词汇:")
        for v in vocabulary:
            print(f"   - {v['word']}")

        # 4. 滚动抽屉到底部，找到核心词汇
        print("\n4. 查找核心词汇...")
        drawer = page.locator('div[style*="border-left"]').first
        if drawer:
            # 滚动抽屉内容
            drawer.evaluate('el => el.scrollTop = el.scrollHeight')
            page.wait_for_timeout(1000)

        # 5. 点击词汇列表中的 education
        print("\n5. 点击 education 词汇...")
        vocab_items = page.locator('.ant-list-item').all()
        print(f"   找到 {len(vocab_items)} 个词汇项")

        if vocab_items:
            vocab_items[0].click()  # education 是第一个
            page.wait_for_timeout(1500)
            page.screenshot(path='/tmp/cloze_highlighted.png', full_page=True)
            print("   高亮截图: /tmp/cloze_highlighted.png")

            # 获取高亮元素
            highlighted = page.locator('mark').all()
            print(f"   高亮元素数量: {len(highlighted)}")
            if highlighted:
                for i, h in enumerate(highlighted[:5]):
                    text = h.inner_text()
                    print(f"   高亮文本 [{i}]: '{text}'")

        print("\n6. 保持浏览器打开 15 秒供观察...")
        page.wait_for_timeout(15000)

        browser.close()
        print("\n调试完成!")

if __name__ == '__main__':
    debug_highlight()
