#!/usr/bin/env python3
"""调试LLM编码问题"""

import requests
import json

API_URL = "https://coding.dashscope.aliyuncs.com/v1/chat/completions"
API_KEY = "YOUR_API_KEY_HERE"
MODEL = "glm-4.7"

prompt = """你是一个HR助手。请用JSON格式回答：
{"score": 80, "recommend": "推荐"}
"""

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json; charset=utf-8"
}

data = {
    "model": MODEL,
    "messages": [{"role": "user", "content": prompt}],
    "temperature": 0.3,
    "max_tokens": 100
}

print("测试1: 使用 json 参数")
try:
    response = requests.post(API_URL, headers=headers, json=data, timeout=30)
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.text[:200]}")
except Exception as e:
    print(f"错误: {e}")

print("\n测试2: 使用 data 参数 + encode")
try:
    response = requests.post(
        API_URL, 
        headers=headers, 
        data=json.dumps(data, ensure_ascii=False).encode('utf-8'),
        timeout=30
    )
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.text[:200]}")
except Exception as e:
    print(f"错误: {e}")

print("\n测试3: 简单请求")
try:
    response = requests.post(
        API_URL,
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"model": MODEL, "messages": [{"role": "user", "content": "你好"}]},
        timeout=30
    )
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.text[:300]}")
except Exception as e:
    print(f"错误: {type(e).__name__}: {e}")