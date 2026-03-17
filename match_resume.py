#!/usr/bin/env python3
"""
简历与岗位匹配 - 使用LLM
"""

import json
import os
import requests

API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
API_KEY = "YOUR_API_KEY_HERE"  # 请替换为你的 API Key
MODEL = "glm-4.7"

def load_jobs(jobs_file="jobs.json"):
    jobs_path = os.path.join(os.path.dirname(__file__), jobs_file)
    with open(jobs_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_resume(resume_file):
    with open(resume_file, 'r', encoding='utf-8') as f:
        return f.read()

def match_resume_to_job(resume_text, job_name, job_description):
    prompt = f"""你是一个专业的HR招聘助手。请分析以下应聘者简历与岗位要求的匹配度。

## 岗位名称
{job_name}

## 岗位要求
{job_description}

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
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content']
    except Exception as e:
        return f"LLM调用失败: {e}"

def match_all_jobs(resume_text, jobs=None):
    if jobs is None:
        jobs = load_jobs()
    
    results = []
    
    for job in jobs:
        print(f"正在匹配: {job['name']}...")
        analysis = match_resume_to_job(resume_text, job['name'], job['description'])
        
        score = 0
        for line in analysis.split('\n'):
            if '匹配度评分' in line or '评分' in line:
                import re
                scores = re.findall(r'\d+', line)
                if scores:
                    score = int(scores[0])
        
        results.append({
            'job_name': job['name'],
            'score': score,
            'analysis': analysis
        })
        
        print(f"  匹配度: {score}分")
    
    results.sort(key=lambda x: x['score'], reverse=True)
    
    return results

def main():
    resume_file = os.path.join(os.path.dirname(__file__), "resumes", "test_resume.txt")
    
    if not os.path.exists(resume_file):
        print(f"简历文件不存在: {resume_file}")
        return
    
    print("加载简历...")
    resume_text = load_resume(resume_file)
    print(f"简历长度: {len(resume_text)} 字符")
    
    print("\n加载岗位列表...")
    jobs = load_jobs()
    print(f"共 {len(jobs)} 个岗位")
    
    print("\n开始匹配分析...\n")
    results = match_all_jobs(resume_text, jobs)
    
    print("\n" + "="*60)
    print("匹配结果排名 (按匹配度降序)")
    print("="*60)
    
    for i, result in enumerate(results[:5], 1):
        print(f"\n{i}. {result['job_name']} - 匹配度: {result['score']}分")
    
    output_file = os.path.join(os.path.dirname(__file__), "match_results.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n详细结果已保存到: {output_file}")
    
    print("\n" + "="*60)
    print("最佳匹配岗位详情")
    print("="*60)
    if results:
        print(results[0]['analysis'])

if __name__ == "__main__":
    main()