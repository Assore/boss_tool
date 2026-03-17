#!/bin/bash
cd "$(dirname "$0")"

echo "=========================================="
echo "  BOSS直聘自动回复工具 - 依赖安装"
echo "=========================================="
echo ""

echo "正在安装依赖..."
pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "  ✅ 安装成功！"
    echo "  现在可以双击「启动.command」使用了"
    echo "=========================================="
else
    echo ""
    echo "❌ 依赖安装失败，请检查网络或Python环境"
fi

echo ""
echo "按任意键关闭..."
read -n 1