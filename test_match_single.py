#!/usr/bin/env python3
"""测试单个岗位匹配"""

import json
import os
import re
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

# 模拟从会话中提取的岗位名称
job_name = "研发助理实习生"

print(f"应聘者应聘岗位: {job_name}")
print(f"简历长度: {len(resume_text)} 字符")

# 查找对应岗位
job = None
for j in jobs:
    if j['name'] == job_name or job_name in j['name'] or j['name'] in job_name:
        job = j
        break

if not job:
    print(f"未找到岗位: {job_name}")
    exit(1)

print(f"匹配到岗位: {job['name']}")
print("\n调用LLM匹配...")

prompt = f"""你是一个专业的HR招聘助手。请分析以下应聘者简历与岗位要求的匹配度。

## 岗位名称
{job['name']}

## 岗位要求
{job['description']}

## 应聘者简历
{resume_text}

请严格按照以下JSON格式输出，不要输出其他内容：
{{"score": 匹配度评分(0-100的整数), "match_skills": "技能匹配分析(一句话)", "match_exp": "经验匹配分析(一句话)", "match_edu": "学历匹配分析(一句话)", "pros": "优势(一句话)", "cons": "不足(一句话)", "recommend": "推荐/不推荐/待定"}}
"""

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

data = {
    "model": MODEL,
    "messages": [{"role": "user", "content": prompt}],
    "temperature": 0.3,
    "max_tokens": 500
}

try:
    response = requests.post(API_URL, headers=headers, json=data, timeout=30)
    print(f"HTTP状态码: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        content = result['choices'][0]['message']['content']
        print("\n" + "="*60)
        print("LLM返回:")
        print("="*60)
        print(content)
        
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            print("\n" + "="*60)
            print("解析结果:")
            print("="*60)
            print(f"匹配度评分: {parsed.get('score', 0)} 分")
            print(f"技能匹配: {parsed.get('match_skills', '')}")
            print(f"经验匹配: {parsed.get('match_exp', '')}")
            print(f"学历匹配: {parsed.get('match_edu', '')}")
            print(f"优势: {parsed.get('pros', '')}")
            print(f"不足: {parsed.get('cons', '')}")
            print(f"建议: {parsed.get('recommend', '')}")
    else:
        print(f"错误: {response.text}")
except Exception as e:
    print(f"错误: {e}")