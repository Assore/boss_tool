#!/usr/bin/env python3
"""检查简历弹窗内部滚动区域"""

from playwright.sync_api import sync_playwright

print("连接Chrome...")
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9223")
    contexts = browser.contexts
    page = contexts[0].pages[0] if contexts[0].pages else contexts[0].new_page()
    
    popup = page.locator('[class*="popup"]').first
    print(f"弹窗存在: {popup.count() > 0}")
    
    scroll_info = popup.evaluate('''el => {
        const results = [];
        
        function findScrollable(element, depth = 0) {
            if (depth > 5) return;
            
            const style = window.getComputedStyle(element);
            const tagName = element.tagName.toLowerCase();
            const className = element.className || '';
            
            if (style.overflow === 'auto' || style.overflow === 'scroll' || 
                style.overflowY === 'auto' || style.overflowY === 'scroll') {
                results.push({
                    tag: tagName,
                    className: className.substring(0, 50),
                    scrollHeight: element.scrollHeight,
                    clientHeight: element.clientHeight,
                    scrollWidth: element.scrollWidth,
                    clientWidth: element.clientWidth,
                    depth: depth
                });
            }
            
            for (let child of element.children) {
                findScrollable(child, depth + 1);
            }
        }
        
        findScrollable(el);
        return results;
    }''')
    
    print("\n可滚动元素:")
    for info in scroll_info:
        if info['scrollHeight'] > info['clientHeight']:
            print(f"  depth={info['depth']}: {info['tag']}.{info['className']}")
            print(f"    垂直滚动: {info['scrollHeight']} > {info['clientHeight']} (需要滚动)")
        elif info['scrollWidth'] > info['clientWidth']:
            print(f"  depth={info['depth']}: {info['tag']}.{info['className']}")
            print(f"    水平滚动: {info['scrollWidth']} > {info['clientWidth']}")
    
    print("\n检查简历内容区块...")
    content_blocks = popup.evaluate('''el => {
        const blocks = el.querySelectorAll('[class*="work"], [class*="project"], [class*="edu"], [class*="experience"]');
        return Array.from(blocks).map(b => ({
            className: b.className.substring(0, 50),
            text: b.innerText.substring(0, 100)
        }));
    }''')
    
    for block in content_blocks:
        print(f"  {block['className']}: {block['text'][:50]}...")