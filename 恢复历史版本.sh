#!/bin/bash

# BOSS直聘自动回复工具 - 历史版本恢复
# 使用方法: ./恢复历史版本.sh

cd "$(dirname "$0")"

echo "=========================================="
echo "  BOSS直聘自动回复工具 - 历史版本恢复"
echo "=========================================="
echo ""

# 先拉取最新
echo "🔄 同步远程仓库..."
git fetch origin main 2>/dev/null

# 获取提交历史
echo ""
echo "📜 提交历史:"
echo "------------------------------------------"
git log --oneline -20
echo "------------------------------------------"
echo ""

# 选择版本
read -p "请输入要恢复的版本号(前几位即可，如 9bb644c)，或按回车取消: " commit_hash

if [ -z "$commit_hash" ]; then
    echo "❌ 已取消"
    exit 0
fi

# 验证版本号
if ! git rev-parse "$commit_hash" >/dev/null 2>&1; then
    echo "❌ 版本号无效"
    exit 1
fi

# 显示该版本信息
echo ""
echo "📋 版本信息:"
git log -1 --format="提交: %h%n作者: %an%n时间: %cd%n说明: %s" --date=format:'%Y-%m-%d %H:%M' "$commit_hash"
echo ""

# 选择操作
echo "请选择操作:"
echo "  1) 查看该版本的文件内容（不修改当前文件）"
echo "  2) 恢复到该版本（覆盖当前文件）"
echo "  3) 下载该版本到新文件夹"
echo ""
read -p "请选择 (1/2/3): " action

case $action in
    1)
        echo ""
        echo "📄 该版本的文件列表:"
        echo "------------------------------------------"
        git show --stat "$commit_hash" | head -30
        echo "------------------------------------------"
        echo ""
        read -p "输入文件名查看内容(如 app.py)，或回车退出: " filename
        if [ -n "$filename" ]; then
            git show "$commit_hash:$filename" | less
        fi
        ;;
    2)
        echo ""
        read -p "⚠️ 这将覆盖当前文件，确认恢复? (y/n): " confirm
        if [ "$confirm" = "y" ]; then
            git checkout "$commit_hash" -- .
            echo "✅ 已恢复到版本 $commit_hash"
            echo "💡 如需推送到远程，请运行: git push origin main --force"
        else
            echo "❌ 已取消"
        fi
        ;;
    3)
        backup_dir="boss_tool_$(date '+%Y%m%d_%H%M%S')"
        read -p "下载到哪个文件夹? (默认: $backup_dir): " custom_dir
        dir_name="${custom_dir:-$backup_dir}"
        
        mkdir -p "../$dir_name"
        git archive "$commit_hash" | tar -x -C "../$dir_name"
        echo "✅ 已下载到: ../$dir_name"
        ;;
    *)
        echo "❌ 无效选择"
        ;;
esac