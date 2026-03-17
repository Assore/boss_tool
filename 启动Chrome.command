#!/bin/bash

echo "=========================================="
echo "  启动Chrome浏览器（调试模式）"
echo "=========================================="
echo ""
echo "正在启动..."
echo ""

/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9223 \
  --user-data-dir="$HOME/chrome-debug-profile" \
  "https://www.zhipin.com/web/user/?ka=header-login" &

echo ""
echo "✅ Chrome已启动！"
echo "请在浏览器中登录BOSS直聘"
echo "登录完成后，回到此网页点击「第二步」"
echo ""