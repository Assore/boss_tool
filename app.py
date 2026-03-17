import streamlit as st
from playwright.sync_api import sync_playwright
import time
import json
import os
import re
import sys
import requests
from PIL import Image

RESUME_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resumes")
JOBS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobs.json")
MATCH_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "match_results.json")
RECORD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "processed.json")
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs.json")

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
    
    close_btn = page.locator('[class*="popup"] [class*="close"]').first
    if close_btn.count() > 0:
        close_btn.click()
        time.sleep(0.5)
    else:
        page.keyboard.press('Escape')
    
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
    
    # 流式回调：实时输出 LLM 内容
    current_line = ""
    def on_stream(content):
        nonlocal current_line
        current_line += content
        # 遇到换行或标点时输出
        if content in ['\n', '。', '，', '：', ':', ',', '.']:
            if current_line.strip():
                log(f"    {current_line.strip()}")
            current_line = ""
    
    result = match_resume_llm(
        resume_text, job['name'], job['description'], 
        api_url, api_key, model, custom_prompt, 
        stream_callback=on_stream
    )
    
    # 输出剩余内容
    if current_line.strip():
        log(f"    {current_line.strip()}")
    
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
    browser = playwright_instance.chromium.connect_over_cdp("http://localhost:9222")
    
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

def process_one_session(page, message, processed, log, config, start_index=0):
    items = page.locator('.geek-item-wrap')
    total_items = items.count()
    
    # 统计信息
    skipped_job_filter = 0  # 因岗位不匹配跳过
    skipped_processed = 0   # 因已处理跳过
    skipped_no_job = 0      # 因无法识别岗位跳过
    selected_jobs = config.get('selected_jobs', [])  # 提前获取筛选岗位
    
    # 调试信息：显示遍历范围
    if start_index == 0:
        log(f"📋 会话列表共 {total_items} 个，开始遍历...")
    
    # 统计：收集所有岗位名
    all_job_names = []
    
    for i in range(start_index, total_items):
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
                continue  # 跳过不在筛选列表中的岗位
        elif selected_jobs and not job_name:
            # 有筛选条件但无法识别岗位名，跳过
            skipped_no_job += 1
            continue
        
        if name not in processed:
            log(f"处理会话: {name} (应聘: {job_name if job_name else '未知岗位'})")
            
            items.nth(i).click()
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
            
            return True, name, resume_text, match_result, i + 1  # 返回下一个起始位置
        else:
            skipped_processed += 1
    
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
        current_index = 0  # 追踪当前遍历位置
        
        while success_count + skip_count < config.get('count', 3):
            success, name, resume_text, match_result, next_index = process_one_session(
                page, config.get('message', ''), processed, log, config, current_index
            )
            current_index = next_index
            
            if success:
                skipped = match_result and match_result.get('score', 0) < config.get('threshold', 50)
                if skipped:
                    skip_count += 1
                else:
                    success_count += 1
                
                # 保存日志记录
                log_entry = {
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'session_time': session_start_time,
                    'name': name,
                    'job_name': match_result.get('job_name', '') if match_result else '',
                    'score': match_result.get('score', 0) if match_result else 0,
                    'skipped': skipped,
                    'message_sent': not skipped,
                    'details': match_result.get('details', {}) if match_result else {}
                }
                save_log(log_entry)
                
                time.sleep(2)
            else:
                log("全部会话已处理完毕！")
                break
        
        log("-" * 40)
        log(f"本次发送消息: {success_count} 个, 跳过(匹配度不足): {skip_count} 个")
        
    except Exception as e:
        log(f"错误: {e}")
    
    return results


st.set_page_config(page_title="BOSS直聘自动回复", page_icon="💬", layout="wide")
st.title("💬 BOSS直聘自动回复工具")

tab1, tab2, tab3 = st.tabs(["🚀 自动处理", "📋 会话记录", "📊 处理日志"])

# ==================== Tab 1: 自动处理 ====================
with tab1:
    st.markdown("""
    ### 使用步骤
    1. 双击 `启动Chrome.command` 打开浏览器
    2. 在浏览器中扫码登录BOSS直聘
    3. 配置下方参数后点击开始处理
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.header("基础设置")
        message = st.text_input("发送的消息", value="方便发一份你的简历过来吗？", max_chars=200, key="msg_input")
        count = st.number_input("处理会话数量", min_value=1, max_value=50, value=3, key="count_input")
        read_resume = st.checkbox("读取在线简历", value=True, key="read_resume_cb")
        
        st.divider()
        st.subheader("🎯 岗位筛选")
        job_names = get_job_names()
        if job_names:
            enable_job_filter = st.checkbox("启用岗位筛选", value=False, help="只处理应聘选中岗位的求职者", key="enable_job_filter_cb")
            if enable_job_filter:
                selected_jobs = st.multiselect(
                    "选择要处理的岗位",
                    options=job_names,
                    default=[],
                    help="留空则处理所有岗位",
                    key="job_filter_multiselect"
                )
            else:
                selected_jobs = []
        else:
            st.info("暂无岗位数据，请先在 jobs.json 中添加岗位")
            enable_job_filter = False
            selected_jobs = []
    
    with col2:
        st.header("LLM匹配设置")
        enable_match = st.checkbox("启用智能匹配", value=False, help="启用后将用LLM匹配简历与岗位", key="enable_match_cb")
        api_url = st.text_input("API地址", value="https://coding.dashscope.aliyuncs.com/v1/chat/completions", key="api_url_input")
        api_key = st.text_input("API密钥", value="", type="password", key="api_key_input")
        model = st.text_input("模型名称", value="glm-4.7", key="model_input")
        threshold = st.slider("匹配度阈值", min_value=0, max_value=100, value=50, help="低于此分数的应聘者将被跳过", key="threshold_slider")
        
        st.divider()
        st.subheader("📝 自定义匹配Prompt")
        use_custom_prompt = st.checkbox("使用自定义Prompt", value=False, key="use_custom_prompt_cb")
        if use_custom_prompt:
            custom_prompt = st.text_area(
                "匹配提示词模板",
                value=DEFAULT_MATCH_PROMPT,
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
    
    config = {
        'message': message,
        'count': count,
        'read_resume': read_resume,
        'enable_match': enable_match,
        'api_url': api_url,
        'api_key': api_key,
        'model': model,
        'threshold': threshold,
        'selected_jobs': selected_jobs,
        'custom_prompt': custom_prompt
    }
    
    col_btn1, col_btn2 = st.columns(2)
    
    with col_btn1:
        if st.button("🔗 连接并开始处理", type="primary", use_container_width=True):
            if enable_match and not api_key:
                st.error("请填写API密钥")
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
                    st.error(f"连接失败: {e}\n\n请确保已双击「启动Chrome.command」打开浏览器")
    
    with col_btn2:
        if st.button("🔄 继续处理", use_container_width=True):
            if page_instance is None:
                st.error("请先点击「连接并开始处理」")
            elif enable_match and not api_key:
                st.error("请填写API密钥")
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