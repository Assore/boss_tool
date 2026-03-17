#!/usr/bin/env python3
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    page = browser.contexts[0].pages[0]
    
    popup = page.locator('[class*="popup"]').first
    scrollable = popup.locator('.resume-detail, [class*="resume-detail"], [class*="resume-content"]').first
    
    popup_text = popup.evaluate('''el => {
        const nameEl = el.querySelector('[class*="name"], .geek-name, h3, h2');
        const infoEl = el.querySelector('[class*="info"], .geek-info');
        return {
            name: nameEl ? nameEl.innerText : null,
            info: infoEl ? infoEl.innerText : null,
            popupClasses: el.className,
            scrollableClasses: document.querySelector('.resume-detail, [class*="resume-detail"]')?.className
        };
    }''')
    
    print("弹窗信息:")
    print(f"  姓名元素: {popup_text.get('name')}")
    print(f"  基本信息元素: {popup_text.get('info')}")
    print(f"  弹窗class: {popup_text.get('popupClasses')}")
    print(f"  滚动区class: {popup_text.get('scrollableClasses')}")
    
    scrollable_box = scrollable.bounding_box()
    popup_box = popup.bounding_box()
    print(f"\n弹窗大小: {popup_box}")
    print(f"滚动区大小: {scrollable_box}")
    
    print(f"\n姓名是否在滚动区内: {popup_text.get('name') and '鲁' in str(popup_text.get('name'))}")