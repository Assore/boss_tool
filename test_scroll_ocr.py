#!/usr/bin/env python3
"""测试简历滚动截图+OCR"""

import os
from PIL import Image

def capture_resume_scroll(page, output_path: str):
    popup = page.locator('[class*="popup"]').first
    if popup.count() == 0:
        print("未找到简历弹窗")
        return None
    
    box = popup.bounding_box()
    print(f"弹窗位置: {box}")
    
    scrollable = popup.locator('.resume-detail, [class*="resume-detail"], [class*="resume-content"]').first
    
    try:
        scroll_height = scrollable.evaluate('el => el.scrollHeight')
        client_height = scrollable.evaluate('el => el.clientHeight')
        scrollable_box = scrollable.bounding_box()
    except:
        print("无法获取滚动信息，直接截取整个弹窗")
        screenshot = popup.screenshot()
        with open(output_path, 'wb') as f:
            f.write(screenshot)
        return output_path
    
    print(f"滚动区域: scrollHeight={scroll_height}, clientHeight={client_height}")
    print(f"滚动区位置: y={scrollable_box['y']}, 弹窗y={box['y']}")
    
    header_offset = scrollable_box['y'] - box['y']
    print(f"顶部固定区域高度: {header_offset}px")
    
    scrollable.evaluate('el => el.scrollTo(0, 0)')
    page.wait_for_timeout(500)
    
    images = []
    texts = []
    
    if header_offset > 10:
        print(f"截取顶部固定区域...")
        header_clip = {'x': box['x'], 'y': box['y'], 'width': box['width'], 'height': header_offset}
        header_screenshot = page.screenshot(clip=header_clip)
        header_path = output_path.replace('.png', '_header.png')
        with open(header_path, 'wb') as f:
            f.write(header_screenshot)
        images.append(header_path)
        header_text = ocr_image(header_path)
        texts.append(header_text)
    
    if scroll_height <= client_height:
        print("简历内容无需滚动，直接截图")
        screenshot = scrollable.screenshot()
        temp_path = output_path.replace('.png', f'_{len(images)}.png')
        with open(temp_path, 'wb') as f:
            f.write(screenshot)
        images.append(temp_path)
        texts.append(ocr_image(temp_path))
    else:
        scroll_pos = 0
        scroll_step = int(client_height * 0.7)
        
        while scroll_pos < scroll_height:
            scrollable.evaluate(f'el => el.scrollTo(0, {scroll_pos})')
            page.wait_for_timeout(300)
            
            temp_path = output_path.replace('.png', f'_{len(images)}.png')
            screenshot = scrollable.screenshot()
            with open(temp_path, 'wb') as f:
                f.write(screenshot)
            images.append(temp_path)
            print(f"截取位置 {scroll_pos}/{scroll_height}")
            
            text = ocr_image(temp_path)
            texts.append(text)
            
            scroll_pos += scroll_step
            if scroll_pos >= scroll_height - client_height:
                scrollable.evaluate(f'el => el.scrollTo(0, {scroll_height - client_height})')
                page.wait_for_timeout(300)
                temp_path = output_path.replace('.png', f'_{len(images)}.png')
                screenshot = scrollable.screenshot()
                with open(temp_path, 'wb') as f:
                    f.write(screenshot)
                images.append(temp_path)
                print(f"截取位置 {scroll_height - client_height}/{scroll_height} (底部)")
                text = ocr_image(temp_path)
                texts.append(text)
                break
    
    merged_text = merge_texts(texts)
    
    merged = merge_images(images, output_path)
    for img in images:
        if os.path.exists(img):
            os.remove(img)
    
    txt_path = output_path.replace('.png', '.txt')
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(merged_text)
    print(f"合并文本已保存: {txt_path}")
    
    return output_path

def merge_texts(texts):
    if not texts:
        return ""
    
    result = []
    
    for text in texts:
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            is_duplicate = False
            for existing in result:
                if line == existing:
                    is_duplicate = True
                    break
                if len(line) > 10 and len(existing) > 10:
                    common = sum(1 for a, b in zip(line, existing) if a == b)
                    similarity = common / max(len(line), len(existing))
                    if similarity > 0.85:
                        is_duplicate = True
                        break
            
            if not is_duplicate:
                result.append(line)
    
    return '\n'.join(result)
    
    box = popup.bounding_box()
    print(f"弹窗位置: {box}")
    
    scrollable = popup.locator('.resume-detail, [class*="resume-detail"], [class*="resume-content"]').first
    
    try:
        scroll_height = scrollable.evaluate('el => el.scrollHeight')
        client_height = scrollable.evaluate('el => el.clientHeight')
    except:
        print("无法获取滚动信息，直接截取整个弹窗")
        screenshot = popup.screenshot()
        with open(output_path, 'wb') as f:
            f.write(screenshot)
        return output_path
    
    print(f"滚动区域: scrollHeight={scroll_height}, clientHeight={client_height}")
    
    scrollable.evaluate('el => el.scrollTo(0, 0)')
    page.wait_for_timeout(500)
    
    if scroll_height <= client_height:
        print("简历内容无需滚动，直接截图")
        screenshot = scrollable.screenshot()
        with open(output_path, 'wb') as f:
            f.write(screenshot)
        return output_path
    
    images = []
    scroll_pos = 0
    scroll_step = int(client_height * 0.7)  # 每次滚动70%，保留30%重叠
    
    while scroll_pos < scroll_height:
        scrollable.evaluate(f'el => el.scrollTo(0, {scroll_pos})')
        page.wait_for_timeout(300)
        
        temp_path = output_path.replace('.png', f'_{len(images)}.png')
        screenshot = scrollable.screenshot()
        with open(temp_path, 'wb') as f:
            f.write(screenshot)
        images.append(temp_path)
        print(f"截取位置 {scroll_pos}/{scroll_height}")
        
        scroll_pos += scroll_step
        if scroll_pos >= scroll_height - client_height:
            scrollable.evaluate(f'el => el.scrollTo(0, {scroll_height - client_height})')
            page.wait_for_timeout(300)
            temp_path = output_path.replace('.png', f'_{len(images)}.png')
            screenshot = scrollable.screenshot()
            with open(temp_path, 'wb') as f:
                f.write(screenshot)
            images.append(temp_path)
            print(f"截取位置 {scroll_height - client_height}/{scroll_height} (底部)")
            break
    
    if len(images) > 1:
        merged = merge_images(images, output_path)
        for img in images:
            if os.path.exists(img):
                os.remove(img)
        return merged
    elif len(images) == 1:
        if images[0] != output_path:
            os.rename(images[0], output_path)
        return output_path
    
    return None

def merge_images(image_paths, output_path):
    """垂直拼接多张截图"""
    images = [Image.open(p) for p in image_paths if os.path.exists(p)]
    if not images:
        return None
    
    widths = [img.width for img in images]
    heights = [img.height for img in images]
    
    overlap = int(images[0].height * 0.3)  # 30%重叠避免遗漏
    total_height = sum(heights) - overlap * (len(images) - 1)
    max_width = max(widths)
    
    merged = Image.new('RGB', (max_width, total_height), 'white')
    
    y_offset = 0
    for i, img in enumerate(images):
        if i > 0:
            y_offset -= overlap
        merged.paste(img, (0, y_offset))
        y_offset += img.height
    
    merged.save(output_path)
    print(f"合并 {len(images)} 张截图 -> {output_path}")
    return output_path

def ocr_image(image_path: str) -> str:
    """使用 macOS Vision 框架进行 OCR 识别"""
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

if __name__ == "__main__":
    from playwright.sync_api import sync_playwright
    
    print("连接Chrome...")
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        contexts = browser.contexts
        if not contexts:
            print("错误: 没有找到浏览器上下文")
            exit(1)
        
        page = contexts[0].pages[0] if contexts[0].pages else contexts[0].new_page()
        
        output_path = os.path.join(os.path.dirname(__file__), "resume_full_scrolled.png")
        
        print("开始滚动截图+OCR...")
        result = capture_resume_scroll(page, output_path)
        
        if result:
            print(f"\n截图保存: {result}")
            txt_path = result.replace('.png', '.txt')
            if os.path.exists(txt_path):
                with open(txt_path, 'r', encoding='utf-8') as f:
                    text = f.read()
                print("\n" + "="*60)
                print("识别内容:")
                print("="*60)
                print(text)
        else:
            print("截图失败")