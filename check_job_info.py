#!/usr/bin/env python3
"""检查会话中的岗位信息"""

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9223")
    page = browser.contexts[0].pages[0]
    
    print("检查会话列表中的岗位信息...")
    
    items = page.locator('.geek-item-wrap')
    for i in range(min(3, items.count())):
        text = items.nth(i).inner_text()
        print(f"\n会话 {i+1} 原始文本:")
        print(text)
        print("-" * 40)
    
    print("\n检查聊天区域的岗位信息...")
    
    job_info = page.evaluate('''() => {
        const results = [];
        
        // 查找可能包含岗位信息的元素
        const selectors = [
            '.job-name', '.job-title', '[class*="job"]',
            '.position', '[class*="position"]',
            '.chat-header', '.session-header'
        ];
        
        for (let sel of selectors) {
            const els = document.querySelectorAll(sel);
            for (let el of els) {
                results.push({
                    selector: sel,
                    text: el.innerText.substring(0, 100)
                });
            }
        }
        
        return results;
    }''')
    
    print("找到的岗位相关元素:")
    for info in job_info:
        print(f"  {info['selector']}: {info['text'][:50]}...")
    
    print("\n检查右侧聊天区域的完整结构...")
    chat_info = page.evaluate('''() => {
        const chatArea = document.querySelector('.chat-wrap, .chat-content, [class*="chat"]');
        if (!chatArea) return "未找到聊天区域";
        
        return {
            html: chatArea.innerHTML.substring(0, 500),
            text: chatArea.innerText.substring(0, 300)
        };
    }''')
    
    print("聊天区域文本:")
    print(chat_info.get('text', chat_info) if isinstance(chat_info, dict) else chat_info)