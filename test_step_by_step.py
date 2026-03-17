#!/usr/bin/env python3
"""
分步测试简历获取流程
每一步完成后暂停，等待用户确认
"""

import os
import sys
import time

def get_os():
    if sys.platform.startswith('win'):
        return 'windows'
    elif sys.platform == 'darwin':
        return 'macos'
    else:
        return 'linux'

def ocr_image(image_path: str) -> str:
    system = get_os()
    
    if system == 'macos':
        try:
            import Vision
            from Quartz import CIImage
            from Foundation import NSURL
            
            url = NSURL.fileURLWithPath_(image_path)
            ci_image = CIImage.imageWithContentsOfURL_(url)
            
            if ci_image is None:
                return f"错误: 无法加载图片 {image_path}"
            
            request = Vision.VNRecognizeTextRequest.alloc().init()
            request.setRecognitionLanguages_(["zh-Hans", "zh-Hant", "en"])
            request.setUsesLanguageCorrection_(True)
            
            handler = Vision.VNImageRequestHandler.alloc().initWithCIImage_options_(ci_image, {})
            success, error = handler.performRequests_error_([request], None)
            
            if not success:
                return f"识别失败: {error}"
            
            results = request.results()
            texts = []
            for result in results:
                candidates = result.topCandidates_(1)
                if candidates:
                    texts.append(candidates[0].string())
            
            return "\n".join(texts)
            
        except ImportError:
            return "错误: 请运行 pip install pyobjc-framework-Vision"
        except Exception as e:
            return f"OCR 错误: {e}"
    
    else:
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(image_path)
            return pytesseract.image_to_string(img, lang='chi_sim+eng')
        except ImportError:
            return "错误: 请安装 pytesseract 和 tesseract-ocr"
        except Exception as e:
            return f"OCR 错误: {e}"

def wait_confirm(msg):
    print(f"\n{'='*60}")
    print(f"📍 {msg}")
    print('='*60)
    input("按 Enter 继续...")

def main():
    print(f"检测到系统: {get_os()}")
    print("="*60)
    
    wait_confirm("步骤1: 连接Chrome浏览器")
    
    from playwright.sync_api import sync_playwright
    
    print("正在连接 localhost:9223 ...")
    p = sync_playwright().start()
    browser = p.chromium.connect_over_cdp("http://localhost:9223")
    contexts = browser.contexts
    
    if not contexts:
        print("❌ 错误: 没有找到浏览器上下文")
        print("请确保已启动Chrome调试模式")
        return
    
    page = contexts[0].pages[0] if contexts[0].pages else contexts[0].new_page()
    print(f"✅ 已连接，当前页面: {page.url}")
    
    wait_confirm("步骤2: 获取会话列表")
    
    items = page.locator('.geek-item-wrap')
    count = items.count()
    print(f"找到 {count} 个会话")
    
    if count == 0:
        print("❌ 未找到会话，请确保在BOSS直聘沟通页面")
        return
    
    for i in range(min(3, count)):
        text = items.nth(i).inner_text()
        lines = text.split('\n')
        print(f"  会话{i+1}: {lines[0][:30]}...")
    
    print(f"✅ 会话列表获取成功")
    
    wait_confirm("步骤3: 点击第一个未处理会话")
    
    import re
    for i in range(count):
        text = items.nth(i).inner_text()
        lines = text.split('\n')
        
        if re.match(r'\d{1,2}:\d{2}', lines[0]):
            name = lines[1] if len(lines) > 1 else lines[0]
        else:
            name = lines[2] if len(lines) > 2 else lines[0]
        
        print(f"找到会话: {name}")
        items.nth(i).click()
        print(f"✅ 已点击会话: {name}")
        break
    
    wait_confirm("步骤4: 点击在线简历按钮")
    
    online_resume = page.locator('text=在线简历').first
    if online_resume.count() == 0:
        print("❌ 未找到在线简历按钮")
        return
    
    online_resume.click()
    print("✅ 已点击在线简历")
    time.sleep(2)
    
    wait_confirm("步骤5: 检查简历弹窗")
    
    popup = page.locator('[class*="popup"]').first
    if popup.count() == 0:
        print("❌ 未找到简历弹窗")
        return
    
    box = popup.bounding_box()
    print(f"✅ 找到弹窗: 位置({box['x']:.0f}, {box['y']:.0f}), 大小({box['width']:.0f}x{box['height']:.0f})")
    
    wait_confirm("步骤6: 检查滚动区域")
    
    scrollable = popup.locator('.resume-detail, [class*="resume-detail"], [class*="resume-content"]').first
    if scrollable.count() == 0:
        print("❌ 未找到滚动区域")
        return
    
    scroll_height = scrollable.evaluate('el => el.scrollHeight')
    client_height = scrollable.evaluate('el => el.clientHeight')
    scrollable_box = scrollable.bounding_box()
    
    print(f"滚动区域高度: {scroll_height}px")
    print(f"可见区域高度: {client_height}px")
    print(f"需要滚动: {'是' if scroll_height > client_height else '否'}")
    
    wait_confirm("步骤7: 截取顶部固定区域（姓名等）")
    
    header_offset = scrollable_box['y'] - box['y']
    print(f"顶部固定区域高度: {header_offset}px")
    
    resume_dir = os.path.join(os.path.dirname(__file__), "resumes")
    if not os.path.exists(resume_dir):
        os.makedirs(resume_dir)
    
    if header_offset > 10:
        header_clip = {'x': box['x'], 'y': box['y'], 'width': box['width'], 'height': header_offset}
        header_path = os.path.join(resume_dir, "test_header.png")
        header_screenshot = page.screenshot(clip=header_clip)
        with open(header_path, 'wb') as f:
            f.write(header_screenshot)
        print(f"✅ 已保存: {header_path}")
    else:
        print("无需截取顶部")
    
    wait_confirm("步骤8: 滚动截取简历内容")
    
    scrollable.evaluate('el => el.scrollTo(0, 0)')
    time.sleep(0.5)
    
    images = []
    scroll_pos = 0
    scroll_step = int(client_height * 0.7)
    
    while scroll_pos < scroll_height:
        scrollable.evaluate(f'el => el.scrollTo(0, {scroll_pos})')
        time.sleep(0.3)
        
        temp_path = os.path.join(resume_dir, f"test_{len(images)}.png")
        screenshot = scrollable.screenshot()
        with open(temp_path, 'wb') as f:
            f.write(screenshot)
        images.append(temp_path)
        print(f"  截取位置 {scroll_pos}/{scroll_height} -> {temp_path}")
        
        scroll_pos += scroll_step
        if scroll_pos >= scroll_height - client_height:
            scrollable.evaluate(f'el => el.scrollTo(0, {scroll_height - client_height})')
            time.sleep(0.3)
            temp_path = os.path.join(resume_dir, f"test_{len(images)}.png")
            screenshot = scrollable.screenshot()
            with open(temp_path, 'wb') as f:
                f.write(screenshot)
            images.append(temp_path)
            print(f"  截取位置 {scroll_height - client_height}/{scroll_height} (底部)")
            break
    
    print(f"✅ 共截取 {len(images)} 张图片")
    
    wait_confirm("步骤9: OCR识别所有截图")
    
    all_texts = []
    
    if header_offset > 10:
        header_path = os.path.join(resume_dir, "test_header.png")
        if os.path.exists(header_path):
            print("识别顶部区域...")
            header_text = ocr_image(header_path)
            all_texts.append(header_text)
            print(f"  顶部内容: {header_text[:100]}...")
    
    for img_path in images:
        print(f"识别: {os.path.basename(img_path)}")
        text = ocr_image(img_path)
        all_texts.append(text)
        print(f"  内容长度: {len(text)} 字符")
    
    print(f"✅ OCR识别完成")
    
    wait_confirm("步骤10: 合并文本并保存")
    
    lines_seen = set()
    result_lines = []
    
    for text in all_texts:
        for line in text.split('\n'):
            line = line.strip()
            if line and line not in lines_seen:
                lines_seen.add(line)
                result_lines.append(line)
    
    merged_text = '\n'.join(result_lines)
    
    txt_path = os.path.join(resume_dir, "test_resume.txt")
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(merged_text)
    
    print(f"✅ 已保存: {txt_path}")
    print(f"   总长度: {len(merged_text)} 字符")
    
    wait_confirm("步骤11: 关闭简历弹窗")
    
    close_btn = page.locator('[class*="popup"] [class*="close"]').first
    if close_btn.count() > 0:
        close_btn.click()
        print("✅ 已关闭弹窗")
    else:
        print("未找到关闭按钮，尝试按ESC")
        page.keyboard.press('Escape')
    
    print("\n" + "="*60)
    print("🎉 测试完成！")
    print("="*60)
    print(f"\n简历内容已保存到: {txt_path}")
    
    print("\n简历内容预览:")
    print("-"*60)
    print(merged_text[:500])
    if len(merged_text) > 500:
        print(f"\n... (还有 {len(merged_text)-500} 字符)")

if __name__ == "__main__":
    main()