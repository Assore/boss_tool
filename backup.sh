#!/bin/bash

# BOSS直聘自动回复工具 - 备份脚本
# 使用方法: ./备份.sh

cd "$(dirname "$0")"

echo "=========================================="
echo "  BOSS直聘自动回复工具 - Git 备份"
echo "=========================================="
echo ""

# 检查是否有更改
if git diff --quiet && git diff --staged --quiet; then
    echo "✅ 没有需要备份的更改"
    echo ""
    
    # 询问是否仍然推送
    read -p "是否强制推送到远程? (y/n): " force_push
    if [ "$force_push" = "y" ]; then
        git push origin main
        echo "✅ 已推送到 GitHub"
    fi
    exit 0
fi

# 显示更改的文件
echo "📋 更改的文件:"
echo "------------------------------------------"
git status -s
echo "------------------------------------------"
echo ""

# 输入修改说明
read -p "请输入修改说明: " commit_msg

if [ -z "$commit_msg" ]; then
    commit_msg="更新: $(date '+%Y-%m-%d %H:%M')"
fi

echo ""
echo "📝 修改说明: $commit_msg"
echo ""

# 确认
read -p "确认备份? (y/n): " confirm
if [ "$confirm" != "y" ]; then
    echo "❌ 已取消"
    exit 0
fi

# 执行备份
echo ""
echo "🔄 正在备份..."

git add .
git commit -m "$commit_msg"
git push origin main

echo ""
echo "✅ 备份完成！"
echo "📦 仓库地址: https://github.com/Assore/boss_tool"