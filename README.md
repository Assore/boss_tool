# BOSS直聘自动回复工具

## 安装步骤（只需一次）

### 第一步：安装 Python
如果还没有 Python，请下载安装：
- macOS: `brew install python` 或从 python.org 下载
- Windows: 从 python.org 下载安装包

### 第二步：打开终端，进入此文件夹并安装依赖
```bash
pip install -r requirements.txt
playwright install chromium
```

## 使用方法

### macOS
双击 `启动.command` 文件

### Windows
双击 `启动.bat` 文件

浏览器会自动打开一个网页界面，在那里操作即可。

## 配置 API

如需使用 LLM 智能匹配功能，请编辑 `api_config.json` 文件：

```json
{
  "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
  "api_key": "你的API密钥"
}
```

## 功能

- 自动点击未读消息
- 自动发送自定义消息
- 自动发送简历
- LLM智能匹配简历与岗位
- 岗位筛选功能

## 注意事项

- 首次使用需要扫码登录
- 登录状态会保存，下次无需重新登录
- 如需更换账号，点击「清除登录状态」