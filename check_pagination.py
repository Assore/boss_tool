#!/usr/bin/env python3
"""检查会话列表分页结构"""

from playwright.sync_api import sync_playwright

print("连接Chrome...")
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    contexts = browser.contexts
    page = contexts[0].pages[0] if contexts[0].pages else contexts[0].new_page()
    
    # 检查会话列表区域
    print("\n检查会话列表结构...")
    
    info = page.evaluate('''() => {
        const results = {};
        
        // 检查会话项数量
        const items = document.querySelectorAll('.geek-item-wrap');
        results.session_count = items.length;
        
        // 检查分页元素
        const paginationSelectors = [
            '.pagination', '.pager', '[class*="pagination"]', '[class*="pager"]',
            '.page-btn', '.next-page', '.load-more', '[class*="load-more"]',
            '.scroll-load', '[class*="scroll"]'
        ];
        
        results.pagination_elements = [];
        for (let sel of paginationSelectors) {
            const els = document.querySelectorAll(sel);
            for (let el of els) {
                results.pagination_elements.push({
                    selector: sel,
                    text: el.innerText.substring(0, 50),
                    className: el.className
                });
            }
        }
        
        // 检查会话列表容器
        const listContainer = document.querySelector('.session-list, [class*="session-list"], [class*="chat-list"]');
        if (listContainer) {
            const style = window.getComputedStyle(listContainer);
            results.list_container = {
                className: listContainer.className,
                scrollHeight: listContainer.scrollHeight,
                clientHeight: listContainer.clientHeight,
                overflow: style.overflow,
                overflowY: style.overflowY
            };
        }
        
        // 检查是否有"加载更多"按钮
        const loadMoreBtns = document.querySelectorAll('button, [class*="btn"], [class*="more"]');
        results.load_more_buttons = [];
        for (let btn of loadMoreBtns) {
            const text = btn.innerText;
            if (text.includes('加载') || text.includes('更多') || text.includes('下一页')) {
                results.load_more_buttons.push({
                    text: text,
                    className: btn.className
                });
            }
        }
        
        return results;
    }''')
    
    print(f"当前会话数量: {info['session_count']}")
    
    if info.get('list_container'):
        print(f"\n会话列表容器:")
        print(f"  类名: {info['list_container']['className']}")
        print(f"  滚动高度: {info['list_container']['scrollHeight']}")
        print(f"  可见高度: {info['list_container']['clientHeight']}")
        print(f"  overflow: {info['list_container']['overflow']}")
    
    if info['pagination_elements']:
        print(f"\n分页元素:")
        for el in info['pagination_elements']:
            print(f"  {el['selector']}: {el['text']} ({el['className']})")
    
    if info['load_more_buttons']:
        print(f"\n加载更多按钮:")
        for btn in info['load_more_buttons']:
            print(f"  [{btn['text']}] {btn['className']}")
    
    print("\n检查滚动加载...")
    # 尝试滚动到底部看是否会加载更多
    for i in range(3):
        page.evaluate('''() => {
            const items = document.querySelectorAll('.geek-item-wrap');
            if (items.length > 0) {
                items[items.length - 1].scrollIntoView({behavior: 'instant', block: 'end'});
            }
        }''')
        import time
        time.sleep(0.5)
        new_count = len(page.query_selector_all('.geek-item-wrap'))
        print(f"  滚动 {i+1} 次后: {new_count} 个会话")