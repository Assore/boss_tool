#!/usr/bin/env python3
"""检查简历弹窗结构"""

from playwright.sync_api import sync_playwright

print("连接Chrome...")
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    contexts = browser.contexts
    if not contexts:
        print("错误: 没有找到浏览器上下文")
        exit(1)
    
    page = contexts[0].pages[0] if contexts[0].pages else contexts[0].new_page()
    
    print("\n查找可能的简历容器...")
    
    selectors = [
        '.resume-preview-wrap',
        '.resume-preview',
        '[class*="resume"]',
        '.geek-resume',
        '.resume-box',
        '.dialog-content',
        '.modal-content',
        '[class*="dialog"]',
        '[class*="modal"]',
        '[class*="popup"]',
    ]
    
    for sel in selectors:
        count = page.locator(sel).count()
        if count > 0:
            print(f"  {sel}: {count} 个")
            try:
                el = page.locator(sel).first
                box = el.bounding_box()
                if box:
                    print(f"    位置: x={box['x']:.0f}, y={box['y']:.0f}, w={box['width']:.0f}, h={box['height']:.0f}")
            except:
                pass
    
    print("\n查找可见的弹窗/对话框...")
    visible_popups = page.evaluate('''() => {
        const results = [];
        const elements = document.querySelectorAll('*');
        for (let el of elements) {
            const style = window.getComputedStyle(el);
            if (style.position === 'fixed' || style.position === 'absolute') {
                const rect = el.getBoundingClientRect();
                if (rect.width > 300 && rect.height > 300 && rect.width < 1000 && rect.height < 1000) {
                    results.push({
                        tag: el.tagName,
                        className: el.className,
                        width: rect.width,
                        height: rect.height,
                        x: rect.x,
                        y: rect.y
                    });
                }
            }
        }
        return results;
    }''')
    
    for i, popup in enumerate(visible_popups[:10]):
        print(f"\n弹窗 {i+1}: {popup['tag']}.{popup['className'][:50] if popup['className'] else ''}")
        print(f"  位置: ({popup['x']:.0f}, {popup['y']:.0f}) 大小: {popup['width']:.0f}x{popup['height']:.0f}")