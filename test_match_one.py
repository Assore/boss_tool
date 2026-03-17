#!/usr/bin/env python3
"""测试单个岗位匹配"""

import json
import os
import requests

API_URL = "https://coding.dashscope.aliyuncs.com/v1/chat/completions"
API_KEY = "YOUR_API_KEY_HERE"
MODEL = "glm-4.7"

resume_file = os.path.join(os.path.dirname(__file__), "resumes", "test_resume.txt")
jobs_file = os.path.join(os.path.dirname(__file__), "jobs.json")

with open(resume_file, 'r', encoding='utf-8') as f:
    resume_text = f.read()

with open(jobs_file, 'r', encoding='utf-8') as f:
    jobs = json.load(f)

job = jobs[0]
print(f"岗位: {job['name']}")
print(f"简历长度: {len(resume_text)} 字符")
print("\n调用LLM匹配...")

prompt = f"""你是一个专业的HR招聘助手。请分析以下应聘者简历与岗位要求的匹配度。

## 岗位名称
{job['name']}

## 岗位要求
{job['description']}

## 应聘者简历
{resume_text}

请按以下格式输出分析结果：

### 匹配度评分
给出0-100分的匹配度评分

### 匹配分析
1. **技能匹配**：分析应聘者技能与岗位要求的匹配情况
2. **经验匹配**：分析工作经验是否满足要求
3. **学历匹配**：分析学历背景是否满足要求

### 优势
列出应聘者在这个岗位上的主要优势（2-3点）

### 不足
列出应聘者在这个岗位上的不足或差距（2-3点）

### 建议
给出是否推荐该应聘者的建议（推荐/不推荐/待定），并说明理由
"""

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

data = {
    "model": MODEL,
    "messages": [
        {"role": "user", "content": prompt}
    ],
    "temperature": 0.7,
    "max_tokens": 2000
}

try:
    response = requests.post(API_URL, headers=headers, json=data, timeout=60)
    print(f"HTTP状态码: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        content = result['choices'][0]['message']['content']
        print("\n" + "="*60)
        print("匹配结果:")
        print("="*60)
        print(content)
    else:
        print(f"错误响应: {response.text}")
except Exception as e:
    print(f"错误: {e}")