#!/usr/bin/env python3
"""测试简历截图OCR识别效果"""

import os
import sys

def ocr_image(image_path: str) -> str:
    """使用 macOS Vision 框架进行 OCR 识别"""
    try:
        import Vision
        from Quartz import CIImage
        from Foundation import NSURL
        
        # 创建 CIImage
        url = NSURL.fileURLWithPath_(image_path)
        ci_image = CIImage.imageWithContentsOfURL_(url)
        
        if ci_image is None:
            return f"错误: 无法加载图片 {image_path}"
        
        # 创建文字识别请求
        request = Vision.VNRecognizeTextRequest.alloc().init()
        request.setRecognitionLanguages_(["zh-Hans", "zh-Hant", "en"])
        request.setUsesLanguageCorrection_(True)
        
        # 执行识别
        handler = Vision.VNImageRequestHandler.alloc().initWithCIImage_options_(
            ci_image, {}
        )
        success, error = handler.performRequests_error_([request], None)
        
        if not success:
            return f"识别失败: {error}"
        
        # 提取识别结果
        results = request.results()
        texts = []
        for result in results:
            candidates = result.topCandidates_(1)
            if candidates:
                text = candidates[0].string()
                texts.append(text)
        
        return "\n".join(texts)
        
    except ImportError as e:
        return f"导入错误: {e}\n请确保已安装: pip install pyobjc-framework-Vision"
    except Exception as e:
        return f"OCR 错误: {type(e).__name__}: {e}"


if __name__ == "__main__":
    # 测试简历截图
    test_files = [
        "resume_full.png",
        "resume_detail.png", 
        "resume_popup.png"
    ]
    
    for filename in test_files:
        filepath = os.path.join(os.path.dirname(__file__), filename)
        if os.path.exists(filepath):
            print(f"\n{'='*60}")
            print(f"📄 识别文件: {filename}")
            print('='*60)
            result = ocr_image(filepath)
            print(result)
            print(f"\n{'='*60}")
        else:
            print(f"⚠️ 文件不存在: {filename}")