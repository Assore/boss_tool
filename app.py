import streamlit as st
from playwright.sync_api import sync_playwright
import time
import json
import os
import re
import sys
import requests
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

RESUME_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resumes")
JOBS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobs.json")
MATCH_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "match_results.json")
RECORD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "processed.json")
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs.json")
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui_config.json")
API_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_config.json")

# 可选模型列表
AVAILABLE_MODELS = [
    'qwen3.5-plus',
    'qwen3-max-2026-01-23',
    'qwen3-coder-next',
    'qwen3-coder-plus',
    'glm-5',
    'glm-4.7',
    'kimi-k2.5',
    'MiniMax-M2.5'
]

# 默认API配置
DEFAULT_API_CONFIG = {
    'api_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
    'api_key': ''
}

DEFAULT_CONFIG = {
    'message': '方便发一份你的简历过来吗？',
    'count': 3,
    'read_resume': True,
    'enable_job_filter': False,
    'selected_jobs': [],
    'enable_match': False,
    'model': 'glm-4.7',
    'threshold': 50,
    'use_custom_prompt': False,
    'custom_prompt': '',
    'concurrency': 5
}

def load_ui_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                config = DEFAULT_CONFIG.copy()
                config.update(saved)
                return config
        except:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()

def save_ui_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def load_api_config():
    if os.path.exists(API_CONFIG_FILE):
        try:
            with open(API_CONFIG_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                config = DEFAULT_API_CONFIG.copy()
                config.update(saved)
                return config
        except:
            return DEFAULT_API_CONFIG.copy()
    return DEFAULT_API_CONFIG.copy()

def save_api_config(config):
    with open(API_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def get_os():
    if sys.platform.startswith('win'):
        return 'windows'
    elif sys.platform == 'darwin':
        return 'macos'
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
                return f"错误: 无法加载图片"
            
            request = Vision.VNRecognizeTextRequest.alloc().init()
            request.setRecognitionLanguages_(["zh-Hans", "zh-Hant", "en"])
            request.setUsesLanguageCorrection_(True)
            
            handler = Vision.VNImageRequestHandler.alloc().initWithCIImage_options_(ci_image, {})
            success, error = handler.performRequests_error_([request], None)
            
            if not success:
                return f"识别失败"
            
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
            img = Image.open(image_path)
            return pytesseract.image_to_string(img, lang='chi_sim+eng')
        except ImportError:
            return "错误: 请安装 pytesseract 和 tesseract-ocr"
        except Exception as e:
            return f"OCR 错误: {e}"

def merge_images(image_paths, output_path):
    images = [Image.open(p) for p in image_paths if os.path.exists(p)]
    if not images:
        return None
    
    overlap = int(images[0].height * 0.3)
    total_height = sum(img.height for img in images) - overlap * (len(images) - 1)
    max_width = max(img.width for img in images)
    
    merged = Image.new('RGB', (max_width, total_height), 'white')
    
    y_offset = 0
    for i, img in enumerate(images):
        if i > 0:
            y_offset -= overlap
        merged.paste(img, (0, y_offset))
        y_offset += img.height
    
    merged.save(output_path)
    return output_path

def capture_resume_ocr(page, name, log):
    if not os.path.exists(RESUME_DIR):
        os.makedirs(RESUME_DIR)
    
    log("  点击在线简历...")
    online_resume = page.locator('text=在线简历').first
    if online_resume.count() == 0:
        log("  ⚠️ 未找到在线简历按钮")
        return None
    online_resume.click()
    time.sleep(2)
    
    popup = page.locator('[class*="popup"]').first
    if popup.count() == 0:
        log("  ⚠️ 未找到简历弹窗")
        return None
    
    scrollable = popup.locator('.resume-detail, [class*="resume-detail"], [class*="resume-content"]').first
    
    try:
        scroll_height = scrollable.evaluate('el => el.scrollHeight')
        client_height = scrollable.evaluate('el => el.clientHeight')
        scrollable_box = scrollable.bounding_box()
        popup_box = popup.bounding_box()
    except:
        log("  ⚠️ 无法获取滚动信息")
        screenshot = popup.screenshot()
        img_path = os.path.join(RESUME_DIR, f"{name}_resume.png")
        with open(img_path, 'wb') as f:
            f.write(screenshot)
        text = ocr_image(img_path)
        txt_path = os.path.join(RESUME_DIR, f"{name}_resume.txt")
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(text)
        return text
    
    header_offset = scrollable_box['y'] - popup_box['y']
    log(f"  简历区域: {scroll_height}px, 顶部固定: {header_offset}px")
    
    scrollable.evaluate('el => el.scrollTo(0, 0)')
    time.sleep(0.5)
    
    images = []
    texts = []
    
    if header_offset > 10:
        log("  截取顶部固定区域...")
        header_clip = {'x': popup_box['x'], 'y': popup_box['y'], 'width': popup_box['width'], 'height': header_offset}
        header_screenshot = page.screenshot(clip=header_clip)
        header_path = os.path.join(RESUME_DIR, f"{name}_header.png")
        with open(header_path, 'wb') as f:
            f.write(header_screenshot)
        images.append(header_path)
        header_text = ocr_image(header_path)
        texts.append(header_text)
    
    if scroll_height <= client_height:
        log("  截取简历...")
        screenshot = scrollable.screenshot()
        temp_path = os.path.join(RESUME_DIR, f"{name}_0.png")
        with open(temp_path, 'wb') as f:
            f.write(screenshot)
        images.append(temp_path)
        texts.append(ocr_image(temp_path))
    else:
        log(f"  滚动截取简历 ({scroll_height}px)...")
        scroll_pos = 0
        scroll_step = int(client_height * 0.7)
        
        while scroll_pos < scroll_height:
            scrollable.evaluate(f'el => el.scrollTo(0, {scroll_pos})')
            time.sleep(0.3)
            
            temp_path = os.path.join(RESUME_DIR, f"{name}_{len(images)}.png")
            screenshot = scrollable.screenshot()
            with open(temp_path, 'wb') as f:
                f.write(screenshot)
            images.append(temp_path)
            texts.append(ocr_image(temp_path))
            
            scroll_pos += scroll_step
            if scroll_pos >= scroll_height - client_height:
                scrollable.evaluate(f'el => el.scrollTo(0, {scroll_height - client_height})')
                time.sleep(0.3)
                temp_path = os.path.join(RESUME_DIR, f"{name}_{len(images)}.png")
                screenshot = scrollable.screenshot()
                with open(temp_path, 'wb') as f:
                    f.write(screenshot)
                images.append(temp_path)
                texts.append(ocr_image(temp_path))
                break
    
    lines_seen = set()
    result_lines = []
    for text in texts:
        for line in text.split('\n'):
            line = line.strip()
            if line and line not in lines_seen:
                lines_seen.add(line)
                result_lines.append(line)
    
    merged_text = '\n'.join(result_lines)
    
    if len(images) > 1:
        img_path = os.path.join(RESUME_DIR, f"{name}_resume.png")
        merge_images(images, img_path)
    
    for img in images:
        if os.path.exists(img):
            os.remove(img)
    
    txt_path = os.path.join(RESUME_DIR, f"{name}_resume.txt")
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(merged_text)
    log(f"  ✅ 简历已保存: {name}_resume.txt")
    
    # 关闭简历弹窗 - 直接用 Escape 键最可靠
    try:
        page.keyboard.press('Escape')
        time.sleep(0.5)
        # 检查弹窗是否关闭
        dialog = page.locator('.dialog-wrap.active, [class*="dialog"][class*="active"]').first
        if dialog.count() > 0:
            # 如果还没关闭，再按一次
            page.keyboard.press('Escape')
            time.sleep(0.5)
    except:
        pass
    
    return merged_text

def load_jobs():
    if os.path.exists(JOBS_FILE):
        with open(JOBS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def get_job_names():
    """获取所有岗位名称列表"""
    jobs = load_jobs()
    return [job['name'] for job in jobs if 'name' in job]

DEFAULT_MATCH_PROMPT = """你是一个专业的HR招聘助手。请分析以下应聘者简历与岗位要求的匹配度。

## 岗位名称
{job_name}

## 岗位要求
{job_description}

## 应聘者简历
{resume_text}

请严格按照以下JSON格式输出，不要输出其他内容：
{{"score": 匹配度评分(0-100的整数), "match_skills": "技能匹配分析(一句话)", "match_exp": "经验匹配分析(一句话)", "match_edu": "学历匹配分析(一句话)", "pros": "优势(一句话)", "cons": "不足(一句话)", "recommend": "推荐/不推荐/待定"}}
"""

def match_resume_llm(resume_text, job_name, job_description, api_url, api_key, model, custom_prompt=None, stream_callback=None):
    # 自动补全 URL
    if api_url.rstrip('/').endswith('/v1'):
        api_url = api_url.rstrip('/') + '/chat/completions'
    
    if custom_prompt:
        prompt = custom_prompt.format(
            job_name=job_name,
            job_description=job_description,
            resume_text=resume_text
        )
    else:
        prompt = f"""你是一个专业的HR招聘助手。请分析以下应聘者简历与岗位要求的匹配度。

## 岗位名称
{job_name}

## 岗位要求
{job_description}

## 应聘者简历
{resume_text}

请严格按照以下JSON格式输出，不要输出其他内容：
{{"score": 匹配度评分(0-100的整数), "match_skills": "技能匹配分析(一句话)", "match_exp": "经验匹配分析(一句话)", "match_edu": "学历匹配分析(一句话)", "pros": "优势(一句话)", "cons": "不足(一句话)", "recommend": "推荐/不推荐/待定"}}
"""
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 500,
        "stream": True
    }
    
    try:
        # 流式请求
        response = requests.post(
            api_url, 
            headers=headers, 
            data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
            timeout=60,
            stream=True
        )
        response.raise_for_status()
        
        # 收集流式内容
        full_content = ""
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data = line[6:]
                    if data == '[DONE]':
                        break
                    try:
                        chunk = json.loads(data)
                        if 'choices' in chunk and len(chunk['choices']) > 0:
                            delta = chunk['choices'][0].get('delta', {})
                            content = delta.get('content', '')
                            if content:
                                full_content += content
                                if stream_callback:
                                    stream_callback(content)
                    except json.JSONDecodeError:
                        continue
        
        # 解析最终 JSON 结果
        import re
        json_match = re.search(r'\{.*\}', full_content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return {"score": 0, "recommend": "解析失败"}
    except Exception as e:
        return {"score": 0, "recommend": f"LLM错误: {str(e)[:50]}"}

def find_job_by_name(jobs, job_name):
    for job in jobs:
        if job['name'] == job_name:
            return job
        if job_name in job['name'] or job['name'] in job_name:
            return job
    return None

def match_single_job(resume_text, job, api_url, api_key, model, log, custom_prompt=None):
    log(f"  匹配岗位: {job['name']}")
    log(f"  🤖 LLM分析中...")
    
    # 收集流式输出的内容
    collected_content = [""]
    def on_stream(content):
        collected_content[0] += content
    
    result = match_resume_llm(
        resume_text, job['name'], job['description'], 
        api_url, api_key, model, custom_prompt, 
        stream_callback=on_stream
    )
    
    # 输出 LLM 的完整回复
    if collected_content[0]:
        log(f"  📝 LLM回复:")
        for line in collected_content[0].split('\n'):
            if line.strip():
                log(f"     {line.strip()}")
    
    score = result.get('score', 0)
    
    log(f"  ✅ 匹配度: {score}分")
    log(f"    技能: {result.get('match_skills', '-')}")
    log(f"    经验: {result.get('match_exp', '-')}")
    log(f"    学历: {result.get('match_edu', '-')}")
    log(f"    优势: {result.get('pros', '-')}")
    log(f"    不足: {result.get('cons', '-')}")
    log(f"    建议: {result.get('recommend', '-')}")
    
    return {
        'job_name': job['name'],
        'score': score,
        'details': result
    }

page_instance = None
playwright_instance = None
RECORD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "processed.json")

def connect_chrome():
    global page_instance, playwright_instance
    
    playwright_instance = sync_playwright().start()
    browser = playwright_instance.chromium.connect_over_cdp("http://localhost:9223")
    
    contexts = browser.contexts
    if len(contexts) > 0:
        page_instance = contexts[0].pages[0] if contexts[0].pages else contexts[0].new_page()
    else:
        context = browser.new_context()
        page_instance = context.new_page()
    
    return True

def get_processed_list():
    if os.path.exists(RECORD_FILE):
        with open(RECORD_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_processed_list(processed):
    with open(RECORD_FILE, 'w', encoding='utf-8') as f:
        json.dump(processed, f, ensure_ascii=False)

def load_logs():
    """加载所有日志记录"""
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_log(log_entry):
    """保存一条日志记录"""
    logs = load_logs()
    logs.append(log_entry)
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

def click_confirm(page):
    page.evaluate('''() => {
        const tooltip = document.querySelector('.exchange-tooltip');
        if (tooltip) {
            const btns = tooltip.querySelectorAll('span, button, div');
            for (let btn of btns) {
                if (btn.innerText === '确定') {
                    btn.click();
                    break;
                }
            }
        }
    }''')

# ==================== 并发处理相关函数 ====================

def find_next_session(page, processed, selected_jobs, log, start_index=0):
    """
    找到下一个未处理的会话
    返回: (found, index, name, job_name) 或 (False, None, None, None)
    """
    items = page.locator('.geek-item-wrap')
    total_items = items.count()
    
    time_keywords = ['昨天', '前天', '刚刚', '今天', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
    
    def is_time(text):
        if re.match(r'\d{1,2}:\d{2}', text):
            return True
        if text in time_keywords:
            return True
        if re.match(r'^周[一二三四五六日]$', text):
            return True
        if re.match(r'\d{1,2}-\d{1,2}', text):
            return True
        if re.match(r'\d{1,2}月\d{1,2}日', text):
            return True
        return False
    
    i = start_index
    while i < total_items:
        text = items.nth(i).inner_text()
        lines = text.split('\n')
        
        start_idx = 0
        if lines and re.match(r'^\d+$', lines[0]):
            start_idx = 1
        
        if start_idx < len(lines) and is_time(lines[start_idx]):
            name = lines[start_idx + 1] if start_idx + 1 < len(lines) else ""
            job_name = lines[start_idx + 2] if start_idx + 2 < len(lines) else ""
        else:
            name = lines[start_idx] if start_idx < len(lines) else ""
            job_name = lines[start_idx + 1] if start_idx + 1 < len(lines) else ""
        
        if is_time(job_name):
            job_name = ""
        
        # 岗位筛选
        if selected_jobs and job_name:
            job_matched = False
            for selected in selected_jobs:
                selected_keywords = selected.replace("实习生", "").replace("工程师", "").replace("开发", "").replace("算法", "")
                job_keywords = job_name.replace("实习生", "").replace("工程师", "").replace("开发", "").replace("算法", "")
                if (selected_keywords and job_keywords and 
                    (selected_keywords in job_keywords or job_keywords in selected_keywords)):
                    job_matched = True
                    break
                if selected in job_name or job_name in selected:
                    job_matched = True
                    break
            if not job_matched:
                i += 1
                continue
        elif selected_jobs and not job_name:
            i += 1
            continue
        
        if name not in processed:
            return True, i, name, job_name
        
        i += 1
    
    return False, None, None, None

def collect_session_info(page, index, log):
    """
    点击会话并读取简历
    返回: (name, job_name, resume_text) 或 (None, None, None) 如果失败
    """
    items = page.locator('.geek-item-wrap')
    
    # 关闭可能存在的弹窗
    try:
        dialog = page.locator('.dialog-wrap.active, [class*="dialog"][class*="active"]').first
        if dialog.count() > 0:
            page.keyboard.press('Escape')
            time.sleep(0.5)
    except:
        pass
    
    # 获取会话信息
    text = items.nth(index).inner_text()
    lines = text.split('\n')
    
    time_keywords = ['昨天', '前天', '刚刚', '今天', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
    
    def is_time(t):
        if re.match(r'\d{1,2}:\d{2}', t):
            return True
        if t in time_keywords:
            return True
        if re.match(r'^周[一二三四五六日]$', t):
            return True
        if re.match(r'\d{1,2}-\d{1,2}', t):
            return True
        if re.match(r'\d{1,2}月\d{1,2}日', t):
            return True
        return False
    
    start_idx = 0
    if lines and re.match(r'^\d+$', lines[0]):
        start_idx = 1
    
    if start_idx < len(lines) and is_time(lines[start_idx]):
        name = lines[start_idx + 1] if start_idx + 1 < len(lines) else ""
        job_name = lines[start_idx + 2] if start_idx + 2 < len(lines) else ""
    else:
        name = lines[start_idx] if start_idx < len(lines) else ""
        job_name = lines[start_idx + 1] if start_idx + 1 < len(lines) else ""
    
    if is_time(job_name):
        job_name = ""
    
    # 点击会话
    try:
        items.nth(index).click(force=True)
    except:
        items.nth(index).evaluate('el => el.click()')
    time.sleep(2)
    
    # 读取简历
    resume_text = None
    if name:
        resume_text = capture_resume_ocr(page, name, log)
    
    return name, job_name, resume_text

def send_message_to_session(page, message, log):
    """
    发送消息和简历请求
    """
    input_area = page.locator('[contenteditable="true"]').first
    input_area.click()
    time.sleep(1)
    input_area.fill(message)
    time.sleep(1)
    
    page.locator('div.submit:has-text("发送")').first.click()
    log(f"  ✅ 消息已发送")
    time.sleep(2)
    
    page.locator('text=求简历').first.click()
    time.sleep(1)
    
    click_confirm(page)
    log(f"  ✅ 简历请求已发送")
    time.sleep(1)

def match_single_resume_for_batch(args):
    """
    用于并发调用的单个简历匹配函数
    args: (resume_text, job, api_url, api_key, model, custom_prompt, name, log_lock)
    """
    resume_text, job, api_url, api_key, model, custom_prompt, name, log_lock = args
    
    result = {
        'name': name,
        'job_name': job['name'] if job else '',
        'score': 0,
        'details': {},
        'error': None
    }
    
    if not job:
        result['error'] = '未找到岗位描述'
        return result
    
    try:
        # 不使用流式输出，直接获取结果
        match_result = match_resume_llm(
            resume_text, job['name'], job['description'],
            api_url, api_key, model, custom_prompt,
            stream_callback=None
        )
        result['score'] = match_result.get('score', 0)
        result['details'] = match_result
    except Exception as e:
        result['error'] = str(e)[:50]
    
    return result

def batch_match_resumes(resume_data_list, api_url, api_key, model, custom_prompt, log, max_workers=5):
    """
    并发匹配多个简历
    resume_data_list: [(name, job_name, resume_text), ...]
    返回: {name: match_result, ...}
    """
    jobs = load_jobs()
    
    # 准备并发任务参数
    task_args = []
    for name, job_name, resume_text in resume_data_list:
        if not resume_text:
            continue
        job = find_job_by_name(jobs, job_name) if job_name else None
        task_args.append((resume_text, job, api_url, api_key, model, custom_prompt, name, None))
    
    if not task_args:
        return {}
    
    log(f"🚀 开始并发匹配 {len(task_args)} 份简历...")
    
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_name = {
            executor.submit(match_single_resume_for_batch, args): args[6]  # args[6] is name
            for args in task_args
        }
        
        # 收集结果
        completed = 0
        for future in as_completed(future_to_name):
            name = future_to_name[future]
            try:
                result = future.result()
                results[name] = result
                completed += 1
                
                # 输出详细匹配结果
                details = result.get('details', {})
                log(f"  [{completed}/{len(task_args)}] {name}: {result['score']}分")
                if details:
                    log(f"      技能: {details.get('match_skills', '-')}")
                    log(f"      经验: {details.get('match_exp', '-')}")
                    log(f"      学历: {details.get('match_edu', '-')}")
                    log(f"      优势: {details.get('pros', '-')}")
                    log(f"      不足: {details.get('cons', '-')}")
                    log(f"      建议: {details.get('recommend', '-')}")
            except Exception as e:
                results[name] = {'name': name, 'score': 0, 'error': str(e)[:50]}
                completed += 1
                log(f"  [{completed}/{len(task_args)}] {name}: 匹配失败 - {str(e)[:30]}")
    
    return results

def process_one_session(page, message, processed, log, config, start_index=0):
    items = page.locator('.geek-item-wrap')
    total_items = items.count()
    
    # 统计信息
    skipped_job_filter = 0  # 因岗位不匹配跳过
    skipped_processed = 0   # 因已处理跳过
    skipped_no_job = 0      # 因无法识别岗位跳过
    selected_jobs = config.get('selected_jobs', [])  # 提前获取筛选岗位
    
    # 调试信息
    if start_index == 0:
        log(f"📋 当前可见会话: {total_items} 个")
    
    # 统计：收集所有岗位名
    all_job_names = []
    
    i = start_index
    while i < total_items:
        text = items.nth(i).inner_text()
        lines = text.split('\n')
        
        # 解析会话行结构
        # 格式1: 时间 / 名字 / 岗位名 / 消息...
        # 格式2: 未读数 / 时间 / 名字 / 岗位名 / 消息...
        
        # 定义时间格式：HH:MM 或 关键词
        time_keywords = ['昨天', '前天', '刚刚', '今天', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
        
        def is_time(text):
            if re.match(r'\d{1,2}:\d{2}', text):
                return True
            if text in time_keywords:
                return True
            # 匹配 "周一"、"周二" 等
            if re.match(r'^周[一二三四五六日]$', text):
                return True
            # 匹配 "03-15" 这种日期格式
            if re.match(r'\d{1,2}-\d{1,2}', text):
                return True
            # 匹配 "03月13日" 这种格式
            if re.match(r'\d{1,2}月\d{1,2}日', text):
                return True
            return False
        
        start_idx = 0
        if lines and re.match(r'^\d+$', lines[0]):
            start_idx = 1  # 跳过未读数量
        
        if start_idx < len(lines) and is_time(lines[start_idx]):
            # 第start_idx行是时间
            name = lines[start_idx + 1] if start_idx + 1 < len(lines) else ""
            job_name = lines[start_idx + 2] if start_idx + 2 < len(lines) else ""
        else:
            # 没有时间，直接是名字
            name = lines[start_idx] if start_idx < len(lines) else ""
            job_name = lines[start_idx + 1] if start_idx + 1 < len(lines) else ""
        
        # 过滤掉时间格式的"岗位名"
        if is_time(job_name):
            job_name = ""
        
        # 收集岗位名用于统计
        if job_name:
            all_job_names.append(job_name)
        
        # 调试：输出解析结果（仅前5个）
        if start_index == 0 and i < 5:
            log(f"  [调试] 会话{i+1}: name='{name}', job_name='{job_name}', raw_lines={lines[:4]}")
        
        # 岗位筛选（支持关键词匹配）
        if selected_jobs and job_name:
            # 检查job_name是否匹配任何一个选中的岗位（关键词匹配）
            job_matched = False
            matched_with = None
            for selected in selected_jobs:
                # 提取关键词进行匹配（去掉"实习生"、"工程师"等通用词后比较核心词）
                selected_keywords = selected.replace("实习生", "").replace("工程师", "").replace("开发", "").replace("算法", "")
                job_keywords = job_name.replace("实习生", "").replace("工程师", "").replace("开发", "").replace("算法", "")
                
                # 核心词包含匹配，或者原始包含匹配
                if (selected_keywords and job_keywords and 
                    (selected_keywords in job_keywords or job_keywords in selected_keywords)):
                    job_matched = True
                    matched_with = selected
                    break
                # 原始完整匹配
                if selected in job_name or job_name in selected:
                    job_matched = True
                    matched_with = selected
                    break
            
            # 调试：显示匹配结果（仅前5个）
            if start_index == 0 and i < 5:
                log(f"  [调试] 匹配结果: job_matched={job_matched}, matched_with='{matched_with}'")
            
            if not job_matched:
                skipped_job_filter += 1
                i += 1
                continue  # 跳过不在筛选列表中的岗位
        elif selected_jobs and not job_name:
            # 有筛选条件但无法识别岗位名，跳过
            skipped_no_job += 1
            i += 1
            continue
        
        if name not in processed:
            log(f"处理会话: {name} (应聘: {job_name if job_name else '未知岗位'})")
            
            # 先关闭可能存在的弹窗
            try:
                dialog = page.locator('.dialog-wrap.active, [class*="dialog"][class*="active"]').first
                if dialog.count() > 0:
                    page.keyboard.press('Escape')
                    time.sleep(0.5)
            except:
                pass
            
            # 点击会话（使用 force 强制点击，忽略遮挡）
            try:
                items.nth(i).click(force=True)
            except:
                items.nth(i).evaluate('el => el.click()')
            time.sleep(2)
            
            resume_text = None
            match_result = None
            
            if config.get('read_resume', True):
                resume_text = capture_resume_ocr(page, name, log)
                
                if resume_text and config.get('enable_match', False) and job_name:
                    jobs = load_jobs()
                    job = find_job_by_name(jobs, job_name)
                    
                    if job:
                        match_result = match_single_job(
                            resume_text, job,
                            config.get('api_url', ''),
                            config.get('api_key', ''),
                            config.get('model', 'glm-4.7'),
                            log,
                            config.get('custom_prompt')
                        )
                        
                        if match_result['score'] < config.get('threshold', 50):
                            log(f"  ⚠️ 匹配度低于阈值 {config.get('threshold', 50)}分，跳过发送")
                            processed.append(name)
                            save_processed_list(processed)
                            return True, name, resume_text, match_result, i + 1  # 返回下一个起始位置
                    else:
                        log(f"  ⚠️ 未找到岗位 '{job_name}' 的描述，跳过匹配")
            
            input_area = page.locator('[contenteditable="true"]').first
            input_area.click()
            time.sleep(1)
            input_area.fill(message)
            time.sleep(1)
            
            page.locator('div.submit:has-text("发送")').first.click()
            log(f"  ✅ 消息已发送")
            time.sleep(2)
            
            page.locator('text=求简历').first.click()
            time.sleep(1)
            
            click_confirm(page)
            log(f"  ✅ 简历请求已发送")
            time.sleep(1)
            
            processed.append(name)
            save_processed_list(processed)
            
            # 滚动列表，让新会话进入视野（虚拟滚动机制）
            page.evaluate('''() => {
                const userList = document.querySelector('.user-list');
                if (userList) {
                    userList.scrollTop += 200;  // 向下滚动一点
                }
            }''')
            time.sleep(0.3)
            
            return True, name, resume_text, match_result, 0  # 返回0重新遍历（虚拟滚动后内容变化）
        else:
            skipped_processed += 1
        
        i += 1  # while 循环需要手动递增
    
    # 遍历完毕，显示统计信息
    log(f"📊 遍历完成统计:")
    log(f"   - 总会话数: {total_items}")
    
    # 输出所有岗位名统计
    if all_job_names:
        from collections import Counter
        job_counts = Counter(all_job_names)
        log(f"📋 页面岗位分布:")
        for job, count in job_counts.most_common(20):
            log(f"     {job}: {count}人")
    
    if selected_jobs:
        log(f"   - 岗位不匹配跳过: {skipped_job_filter}")
        log(f"   - 无法识别岗位跳过: {skipped_no_job}")
    log(f"   - 已处理过跳过: {skipped_processed}")
    
    return False, None, None, None, total_items  # 返回总数量表示已遍历完

def run_automation(config, progress_callback=None):
    """
    新的批量处理流程：
    1. 串行收集简历（点击会话 → OCR读取）
    2. 并发LLM匹配
    3. 串行发送消息（根据匹配结果）
    """
    global page_instance
    
    results = []
    processed = get_processed_list()
    
    def log(msg):
        results.append(msg)
        if progress_callback:
            progress_callback(msg)
    
    try:
        page = page_instance
        
        log(f"已处理过的会话: {len(processed)} 个")
        log(f"准备处理: {config.get('count', 3)} 个新会话")
        if config.get('read_resume', True):
            log("📝 将读取在线简历内容")
        if config.get('enable_match', False):
            log(f"🎯 匹配度阈值: {config.get('threshold', 50)}分")
            log(f"⚡ 并发LLM匹配已启用")
        selected_jobs = config.get('selected_jobs', [])
        if selected_jobs:
            log(f"🔍 岗位筛选: {len(selected_jobs)} 个岗位")
            for job in selected_jobs[:5]:
                log(f"   - {job}")
            if len(selected_jobs) > 5:
                log(f"   - ... 等 {len(selected_jobs)} 个岗位")
        log("-" * 40)
        
        success_count = 0
        skip_count = 0
        session_start_time = time.strftime('%Y-%m-%d %H:%M:%S')
        current_index = 0
        no_new_sessions_count = 0
        
        # 批量收集大小（一次收集多少份简历后再并发LLM）
        concurrency = config.get('concurrency', 5)
        batch_size = min(config.get('count', 3), concurrency)  # 最多一次处理 concurrency 个
        
        while success_count + skip_count < config.get('count', 3):
            # ============ 阶段1：批量收集简历 ============
            log(f"📦 开始收集简历（目标: {batch_size} 份）...")
            
            collected_data = []  # [(name, job_name, resume_text, session_index), ...]
            collect_count = 0
            
            while collect_count < batch_size:
                found, index, name, job_name = find_next_session(
                    page, processed, selected_jobs, log, current_index
                )
                
                if found:
                    log(f"  [{collect_count + 1}] 收集: {name} (应聘: {job_name if job_name else '未知'})")
                    
                    # 点击会话并读取简历
                    actual_name, actual_job_name, resume_text = collect_session_info(page, index, log)
                    
                    if actual_name:
                        collected_data.append((actual_name, actual_job_name, resume_text, index))
                        processed.append(actual_name)
                        save_processed_list(processed)  # 立即保存
                        collect_count += 1
                    
                    # 滚动让新会话进入视野
                    page.evaluate('''() => {
                        const userList = document.querySelector('.user-list');
                        if (userList) {
                            userList.scrollTop += 200;
                        }
                    }''')
                    time.sleep(0.3)
                    
                    current_index = 0  # 重置索引，重新遍历
                else:
                    # 当前可见区域没有新会话，尝试滚动
                    log("📥 当前区域已遍历完毕，尝试加载更多会话...")
                    
                    scroll_info = page.evaluate('''() => {
                        const userList = document.querySelector('.user-list');
                        if (userList) {
                            return {
                                scrollTop: userList.scrollTop,
                                scrollHeight: userList.scrollHeight,
                                clientHeight: userList.clientHeight
                            };
                        }
                        return null;
                    }''')
                    
                    if scroll_info:
                        current_scroll_top = scroll_info['scrollTop']
                        max_scroll = scroll_info['scrollHeight'] - scroll_info['clientHeight']
                        
                        log(f"   滚动位置: {current_scroll_top}/{max_scroll}")
                        
                        if current_scroll_top >= max_scroll - 10:
                            no_new_sessions_count += 1
                            log(f"   已到达列表底部")
                            
                            if no_new_sessions_count >= 2:
                                log("✅ 全部会话已处理完毕！")
                                break
                        else:
                            page.evaluate('''() => {
                                const userList = document.querySelector('.user-list');
                                if (userList) {
                                    userList.scrollTop += 500;
                                }
                            }''')
                            time.sleep(1)
                            current_index = 0
                            no_new_sessions_count = 0
                    else:
                        log("⚠️ 无法获取滚动信息，停止处理")
                        break
            
            if not collected_data:
                log("没有收集到新会话，结束处理")
                break
            
            # ============ 阶段2：并发LLM匹配 ============
            match_results = {}
            if config.get('enable_match', False) and config.get('read_resume', True):
                match_results = batch_match_resumes(
                    [(name, job_name, resume) for name, job_name, resume, _ in collected_data],
                    config.get('api_url', ''),
                    config.get('api_key', ''),
                    config.get('model', 'glm-4.7'),
                    config.get('custom_prompt'),
                    log,
                    max_workers=concurrency
                )
            else:
                # 不启用匹配，默认全部通过
                for name, job_name, resume_text, _ in collected_data:
                    match_results[name] = {'name': name, 'job_name': job_name, 'score': 100, 'details': {}}
            
            # ============ 阶段3：串行发送消息 ============
            log("📤 开始发送消息...")
            
            for name, job_name, resume_text, session_index in collected_data:
                match_result = match_results.get(name, {'name': name, 'score': 0, 'error': '未知错误'})
                score = match_result.get('score', 0)
                
                if config.get('enable_match', False) and score < config.get('threshold', 50):
                    log(f"  ⏭️ {name}: 匹配度 {score}分 < 阈值，跳过发送")
                    skip_count += 1
                    
                    # 保存日志
                    log_entry = {
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'session_time': session_start_time,
                        'name': name,
                        'job_name': match_result.get('job_name', job_name),
                        'score': score,
                        'skipped': True,
                        'message_sent': False,
                        'details': match_result.get('details', {})
                    }
                    save_log(log_entry)
                    continue
                
                # 发送消息
                log(f"  📨 {name}: 发送消息...")
                
                # 重新点击会话（因为之前可能关闭了或滚动位置变了）
                items = page.locator('.geek-item-wrap')
                found, new_index, _, _ = find_next_session(page, [n for n in processed if n != name], selected_jobs, log, 0)
                
                if found:
                    try:
                        items.nth(new_index).click(force=True)
                    except:
                        items.nth(new_index).evaluate('el => el.click()')
                    time.sleep(2)
                
                send_message_to_session(page, config.get('message', ''), log)
                success_count += 1
                
                # 保存日志
                log_entry = {
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'session_time': session_start_time,
                    'name': name,
                    'job_name': match_result.get('job_name', job_name),
                    'score': score,
                    'skipped': False,
                    'message_sent': True,
                    'details': match_result.get('details', {})
                }
                save_log(log_entry)
                
                time.sleep(2)
                
                # 滚动
                page.evaluate('''() => {
                    const userList = document.querySelector('.user-list');
                    if (userList) {
                        userList.scrollTop += 200;
                    }
                }''')
                time.sleep(0.3)
            
            # 保存处理列表
            save_processed_list(processed)
            
            # 检查是否达到目标
            if success_count + skip_count >= config.get('count', 3):
                break
        
        log("-" * 40)
        log(f"本次发送消息: {success_count} 个, 跳过(匹配度不足): {skip_count} 个")
        
    except Exception as e:
        log(f"错误: {e}")
        import traceback
        log(traceback.format_exc())
    
    return results


st.set_page_config(page_title="BOSS直聘自动回复", page_icon="💬", layout="wide")
st.title("💬 BOSS直聘自动回复工具")

tab1, tab2, tab3, tab4 = st.tabs(["🚀 自动处理", "📋 会话记录", "📊 处理日志", "💼 岗位管理"])

# ==================== Tab 1: 自动处理 ====================
with tab1:
    st.markdown("### 使用步骤")
    
    # 步骤1：启动Chrome
    st.markdown("**第一步：启动Chrome浏览器**")
    col_chrome, col_restart, col_status = st.columns([1, 1, 2])
    with col_chrome:
        if st.button("🌐 启动Chrome", type="primary", use_container_width=True):
            import subprocess
            import platform
            
            chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            if platform.system() == "Windows":
                chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            
            try:
                subprocess.Popen([
                    chrome_path,
                    "--remote-debugging-port=9223",
                    "--user-data-dir=" + os.path.expanduser("~/chrome-debug-profile"),
                    "https://www.zhipin.com/web/user/?ka=header-login"
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                st.success("✅ Chrome已启动！请在浏览器中登录BOSS直聘")
            except Exception as e:
                st.error(f"启动失败: {e}")
    
    with col_restart:
        if st.button("🔄 完全重启", type="secondary", use_container_width=True):
            st.warning("正在重启应用...")
            st.rerun()
    
    with col_status:
        st.info("💡 启动后请在浏览器中扫码登录BOSS直聘，登录完成后，进入**新招呼**界面，继续下一步")
    
    st.divider()
    
    # 步骤2：配置并处理
    st.markdown("**第二步：配置参数并开始处理**")
    
    # 加载配置
    saved_config = load_ui_config()
    api_config = load_api_config()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.header("基础设置")
        message = st.text_input("发送的消息", value=saved_config.get('message', '方便发一份你的简历过来吗？'), max_chars=200, key="msg_input")
        count = st.number_input("处理会话数量", min_value=1, max_value=50, value=saved_config.get('count', 3), key="count_input")
        read_resume = st.checkbox("读取在线简历", value=saved_config.get('read_resume', True), key="read_resume_cb")
        
        st.divider()
        st.subheader("🎯 岗位筛选")
        job_names = get_job_names()
        if job_names:
            enable_job_filter = st.checkbox("启用岗位筛选", value=saved_config.get('enable_job_filter', False), help="只处理应聘选中岗位的求职者", key="enable_job_filter_cb")
            if enable_job_filter:
                selected_jobs = st.multiselect(
                    "选择要处理的岗位",
                    options=job_names,
                    default=saved_config.get('selected_jobs', []),
                    help="留空则处理所有岗位",
                    key="job_filter_multiselect"
                )
            else:
                selected_jobs = []
        else:
            st.info("暂无岗位数据，请先在岗位管理中添加岗位")
            enable_job_filter = False
            selected_jobs = []
    
    with col2:
        st.header("LLM匹配设置")
        enable_match = st.checkbox("启用智能匹配", value=saved_config.get('enable_match', False), help="启用后将用LLM匹配简历与岗位", key="enable_match_cb")
        
        if enable_match:
            saved_model = saved_config.get('model', 'glm-4.7')
            default_index = AVAILABLE_MODELS.index(saved_model) if saved_model in AVAILABLE_MODELS else 0
            model = st.selectbox(
                "选择模型",
                options=AVAILABLE_MODELS,
                index=default_index,
                key="model_select"
            )
        else:
            model = saved_config.get('model', 'glm-4.7')
        
        threshold = st.slider("匹配度阈值", min_value=0, max_value=100, value=saved_config.get('threshold', 50), help="低于此分数的应聘者将被跳过", key="threshold_slider")
        
        concurrency = st.slider("并发数", min_value=1, max_value=10, value=saved_config.get('concurrency', 5), help="同时处理简历的数量，越大速度越快但API压力越大", key="concurrency_slider")
        
        st.divider()
        st.subheader("📝 自定义匹配Prompt")
        use_custom_prompt = st.checkbox("使用自定义Prompt", value=saved_config.get('use_custom_prompt', False), key="use_custom_prompt_cb")
        if use_custom_prompt:
            saved_custom_prompt = saved_config.get('custom_prompt', '')
            prompt_value = saved_custom_prompt if saved_custom_prompt else DEFAULT_MATCH_PROMPT
            custom_prompt = st.text_area(
                "匹配提示词模板",
                value=prompt_value,
                height=300,
                help="使用 {job_name}, {job_description}, {resume_text} 作为占位符",
                key="custom_prompt_area"
            )
        else:
            custom_prompt = None
        
        st.divider()
        processed = get_processed_list()
        st.write(f"已处理会话: {len(processed)} 个")
        
        if st.button("🗑️ 清除处理记录"):
            save_processed_list([])
            st.rerun()
    
    # 保存当前配置
    current_config = {
        'message': message,
        'count': count,
        'read_resume': read_resume,
        'enable_job_filter': enable_job_filter,
        'selected_jobs': selected_jobs,
        'enable_match': enable_match,
        'model': model,
        'threshold': threshold,
        'use_custom_prompt': use_custom_prompt,
        'custom_prompt': custom_prompt if custom_prompt else '',
        'concurrency': concurrency
    }
    
    if current_config != saved_config:
        save_ui_config(current_config)
    
    # 构建完整配置（包含API配置）
    config = {
        'message': message,
        'count': count,
        'read_resume': read_resume,
        'enable_match': enable_match,
        'api_url': api_config.get('api_url', ''),
        'api_key': api_config.get('api_key', ''),
        'model': model,
        'threshold': threshold,
        'selected_jobs': selected_jobs,
        'custom_prompt': custom_prompt,
        'concurrency': concurrency
    }
    
    col_btn1, col_btn2 = st.columns(2)
    
    with col_btn1:
        if st.button("🔗 连接并开始处理", type="primary", use_container_width=True):
            if enable_match and not api_config.get('api_key'):
                st.error("请先在 api_config.json 中配置 API 密钥")
            else:
                try:
                    with st.spinner("正在连接Chrome..."):
                        connect_chrome()
                    st.info("正在执行...")
                    log_box = st.empty()
                    all_logs = []
                    
                    def update_log(msg):
                        all_logs.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
                        log_box.code("\n".join(all_logs))
                    
                    run_automation(config, update_log)
                    st.success("执行完毕！")
                except Exception as e:
                    st.error(f"连接失败: {e}\n\n请确保已点击「启动Chrome」按钮")
    
    with col_btn2:
        if st.button("🔄 继续处理", use_container_width=True):
            if page_instance is None:
                st.error("请先点击「连接并开始处理」")
            elif enable_match and not api_config.get('api_key'):
                st.error("请先在 api_config.json 中配置 API 密钥")
            else:
                st.info("正在执行...")
                log_box = st.empty()
                all_logs = []
                
                def update_log(msg):
                    all_logs.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
                    log_box.code("\n".join(all_logs))
                
                run_automation(config, update_log)
                st.success("执行完毕！")

# ==================== Tab 2: 会话记录 ====================
with tab2:
    st.header("已处理会话列表")
    
    processed = get_processed_list()
    
    if not processed:
        st.info("暂无已处理的会话记录")
    else:
        st.write(f"共 {len(processed)} 条记录")
        
        # 搜索和删除
        col_search, col_del = st.columns([3, 1])
        with col_search:
            search_term = st.text_input("搜索姓名", placeholder="输入姓名筛选...", key="search_processed")
        with col_del:
            if st.button("🗑️ 清空所有记录", type="secondary"):
                save_processed_list([])
                st.rerun()
        
        # 显示列表
        filtered = [p for p in processed if search_term.lower() in p.lower()] if search_term else processed
        
        for i, name in enumerate(filtered):
            col_name, col_del = st.columns([4, 1])
            with col_name:
                st.text(f"{i+1}. {name}")
            with col_del:
                if st.button("删除", key=f"del_{i}_{name}"):
                    processed.remove(name)
                    save_processed_list(processed)
                    st.rerun()
    
    st.divider()
    st.header("手动添加会话记录")
    
    with st.form("add_processed_form"):
        new_names = st.text_area("输入姓名（每行一个）", placeholder="张三\n李四\n王五", height=100)
        submitted = st.form_submit_button("添加")
        
        if submitted and new_names.strip():
            names_to_add = [n.strip() for n in new_names.split('\n') if n.strip()]
            current = get_processed_list()
            added_count = 0
            for name in names_to_add:
                if name not in current:
                    current.append(name)
                    added_count += 1
            save_processed_list(current)
            st.success(f"已添加 {added_count} 条记录")
            st.rerun()

# ==================== Tab 3: 处理日志 ====================
with tab3:
    st.header("历史处理日志")
    
    logs = load_logs()
    
    if not logs:
        st.info("暂无处理日志")
    else:
        col_stats, col_clear = st.columns([3, 1])
        with col_stats:
            total = len(logs)
            sent = sum(1 for l in logs if l.get('message_sent', False))
            skipped = sum(1 for l in logs if l.get('skipped', False))
            st.write(f"总计: {total} 条 | 已发送消息: {sent} | 已跳过: {skipped}")
        with col_clear:
            if st.button("🗑️ 清空所有日志"):
                with open(LOG_FILE, 'w', encoding='utf-8') as f:
                    json.dump([], f)
                st.rerun()
        
        st.divider()
        
        # 筛选
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            filter_name = st.text_input("筛选姓名", placeholder="输入姓名...", key="log_filter_name")
        with col_f2:
            filter_session = st.selectbox(
                "会话批次", 
                options=["全部"] + list(set(l.get('session_time', '') for l in logs)),
                key="log_filter_session"
            )
        with col_f3:
            filter_type = st.selectbox(
                "处理结果",
                ["全部", "已发送消息", "已跳过"],
                key="log_filter_type"
            )
        
        # 筛选逻辑
        filtered_logs = logs
        if filter_name:
            filtered_logs = [l for l in filtered_logs if filter_name.lower() in l.get('name', '').lower()]
        if filter_session != "全部":
            filtered_logs = [l for l in filtered_logs if l.get('session_time', '') == filter_session]
        if filter_type == "已发送消息":
            filtered_logs = [l for l in filtered_logs if l.get('message_sent', False)]
        elif filter_type == "已跳过":
            filtered_logs = [l for l in filtered_logs if l.get('skipped', False)]
        
        # 按时间倒序
        filtered_logs = sorted(filtered_logs, key=lambda x: x.get('timestamp', ''), reverse=True)
        
        st.write(f"显示 {len(filtered_logs)} 条记录")
        
        for log in filtered_logs[:100]:  # 限制显示100条
            with st.expander(f"{'📤' if log.get('message_sent') else '⏭️'} {log.get('name', '未知')} - {log.get('timestamp', '')} - 匹配度: {log.get('score', 0)}分"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**应聘岗位**: {log.get('job_name', '未知')}")
                    st.write(f"**匹配分数**: {log.get('score', 0)}分")
                    st.write(f"**处理结果**: {'已发送消息' if log.get('message_sent') else '已跳过'}")
                with col2:
                    details = log.get('details', {})
                    if details:
                        st.write(f"**技能匹配**: {details.get('match_skills', '-')}")
                        st.write(f"**经验匹配**: {details.get('match_exp', '-')}")
                        st.write(f"**学历匹配**: {details.get('match_edu', '-')}")
                        st.write(f"**优势**: {details.get('pros', '-')}")
                        st.write(f"**不足**: {details.get('cons', '-')}")
                        st.write(f"**建议**: {details.get('recommend', '-')}")

# ==================== Tab 4: 岗位管理 ====================
with tab4:
    st.header("💼 岗位管理")
    
    jobs = load_jobs()
    
    col_info, col_add = st.columns([2, 1])
    
    with col_info:
        st.subheader(f"📋 当前岗位列表 ({len(jobs)} 个)")
        
        search_job = st.text_input("搜索岗位", placeholder="输入岗位名称...", key="job_search")
        
        filtered_jobs = jobs
        if search_job:
            filtered_jobs = [j for j in jobs if search_job.lower() in j['name'].lower()]
        
        for i, job in enumerate(filtered_jobs):
            with st.expander(f"📌 {job['name']}", expanded=False):
                st.markdown("**岗位描述:**")
                st.text(job.get('description', '暂无描述')[:500] + ("..." if len(job.get('description', '')) > 500 else ""))
                
                col_edit, col_del = st.columns(2)
                with col_edit:
                    if st.button("✏️ 编辑", key=f"edit_job_{i}"):
                        st.session_state['editing_job'] = job['name']
                        st.session_state['editing_desc'] = job.get('description', '')
                        st.rerun()
                with col_del:
                    if st.button("🗑️ 删除", key=f"del_job_{i}"):
                        jobs = [j for j in jobs if j['name'] != job['name']]
                        with open(JOBS_FILE, 'w', encoding='utf-8') as f:
                            json.dump(jobs, f, ensure_ascii=False, indent=2)
                        st.success(f"已删除: {job['name']}")
                        st.rerun()
    
    with col_add:
        st.subheader("➕ 添加新岗位")
        
        def clear_form():
            st.session_state['new_job_name'] = ''
            st.session_state['new_job_desc'] = ''
        
        with st.form("add_job_form", clear_on_submit=True):
            new_job_name = st.text_input("岗位名称 *", placeholder="如: 算法工程师", key="new_job_name")
            new_job_desc = st.text_area("岗位描述 *", placeholder="粘贴岗位描述...", height=200, key="new_job_desc")
            
            submitted = st.form_submit_button("添加岗位", type="primary")
            
            if submitted:
                if not new_job_name.strip():
                    st.error("请输入岗位名称")
                elif not new_job_desc.strip():
                    st.error("请输入岗位描述")
                elif any(j['name'] == new_job_name.strip() for j in jobs):
                    st.error(f"岗位 '{new_job_name}' 已存在")
                else:
                    jobs.append({
                        'name': new_job_name.strip(),
                        'description': new_job_desc.strip()
                    })
                    with open(JOBS_FILE, 'w', encoding='utf-8') as f:
                        json.dump(jobs, f, ensure_ascii=False, indent=2)
                    st.success(f"✅ 已添加: {new_job_name}")
                    st.rerun()
        
        st.divider()
        
        if 'editing_job' in st.session_state:
            st.subheader("✏️ 编辑岗位")
            st.info(f"正在编辑: {st.session_state['editing_job']}")
            
            with st.form("edit_job_form"):
                edit_name = st.text_input("岗位名称", value=st.session_state['editing_job'], key="edit_job_name")
                edit_desc = st.text_area("岗位描述", value=st.session_state.get('editing_desc', ''), height=200, key="edit_job_desc")
                
                col_save, col_cancel = st.columns(2)
                with col_save:
                    save_btn = st.form_submit_button("💾 保存", type="primary")
                with col_cancel:
                    cancel_btn = st.form_submit_button("❌ 取消")
                
                if save_btn:
                    for j in jobs:
                        if j['name'] == st.session_state['editing_job']:
                            j['name'] = edit_name.strip()
                            j['description'] = edit_desc.strip()
                            break
                    with open(JOBS_FILE, 'w', encoding='utf-8') as f:
                        json.dump(jobs, f, ensure_ascii=False, indent=2)
                    del st.session_state['editing_job']
                    del st.session_state['editing_desc']
                    st.success("✅ 已保存")
                    st.rerun()
                
                if cancel_btn:
                    del st.session_state['editing_job']
                    if 'editing_desc' in st.session_state:
                        del st.session_state['editing_desc']
                    st.rerun()