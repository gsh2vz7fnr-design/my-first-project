#!/bin/bash

# Claude 技能管理脚本
# 用于快速安装、卸载和管理Claude Code技能

set -e

SKILLS_DIR="$HOME/.config/claude-code/skills"
RESOURCES_DIR="$(cd "$(dirname "$0")" && pwd)"

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# 显示帮助信息
show_help() {
    cat << EOF
Claude 技能管理脚本

用法:
    ./manage-skills.sh [命令] [参数]

命令:
    list                列出所有已安装的技能
    list-available      列出所有可用的技能
    install <skill>     安装指定技能
    uninstall <skill>   卸载指定技能
    update <skill>      更新指定技能
    info <skill>        显示技能信息
    help                显示此帮助信息

示例:
    ./manage-skills.sh list
    ./manage-skills.sh install ui-ux-pro-max
    ./manage-skills.sh uninstall ui-ux-pro-max
    ./manage-skills.sh update ui-ux-pro-max

可用技能:
    ui-ux-pro-max       UI/UX设计智能技能
    superpowers         完整的开发工作流（包含多个子技能）
    document-skills     文档处理技能（docx, pdf, pptx, xlsx）

EOF
}

# 列出已安装的技能
list_installed() {
    print_info "已安装的技能："
    echo ""

    if [ ! -d "$SKILLS_DIR" ]; then
        print_warning "技能目录不存在: $SKILLS_DIR"
        return
    fi

    if [ -z "$(ls -A "$SKILLS_DIR" 2>/dev/null)" ]; then
        print_warning "没有已安装的技能"
        return
    fi

    for skill in "$SKILLS_DIR"/*; do
        if [ -d "$skill" ]; then
            skill_name=$(basename "$skill")
            if [ -f "$skill/SKILL.md" ]; then
                # 提取技能描述
                description=$(grep -m 1 "^description:" "$skill/SKILL.md" | sed 's/description: *"\(.*\)"/\1/' | cut -c1-80)
                echo -e "  ${GREEN}●${NC} ${skill_name}"
                echo -e "    ${description}..."
            else
                echo -e "  ${GREEN}●${NC} ${skill_name}"
            fi
            echo ""
        fi
    done
}

# 列出可用的技能
list_available() {
    print_info "可用的技能："
    echo ""

    # UI/UX Pro Max
    if [ -d "$RESOURCES_DIR/downloaded-skills/ui-ux-pro-max-skill" ]; then
        echo -e "  ${BLUE}○${NC} ui-ux-pro-max"
        echo -e "    UI/UX设计智能 - 67种样式、96种调色板、57种字体配对"
        echo ""
    fi

    # Superpowers
    if [ -d "$RESOURCES_DIR/workflows/superpowers" ]; then
        echo -e "  ${BLUE}○${NC} superpowers"
        echo -e "    完整的软件开发工作流系统"
        echo ""
    fi

    # 官方技能
    if [ -d "$RESOURCES_DIR/official-skills/anthropic-skills/skills" ]; then
        echo -e "  ${BLUE}○${NC} official-skills"
        echo -e "    Anthropic官方技能集合（多个技能）"
        echo ""
    fi
}

# 安装技能
install_skill() {
    local skill_name=$1

    if [ -z "$skill_name" ]; then
        print_error "请指定要安装的技能名称"
        echo "使用 './manage-skills.sh list-available' 查看可用技能"
        exit 1
    fi

    # 创建技能目录
    mkdir -p "$SKILLS_DIR"

    case $skill_name in
        ui-ux-pro-max)
            local source="$RESOURCES_DIR/downloaded-skills/ui-ux-pro-max-skill/.claude/skills/ui-ux-pro-max"
            if [ ! -d "$source" ]; then
                print_error "技能源文件不存在: $source"
                exit 1
            fi

            print_info "正在安装 ui-ux-pro-max..."
            cp -r "$source" "$SKILLS_DIR/"

            # 复制数据和脚本（如果是符号链接）
            if [ -L "$SKILLS_DIR/ui-ux-pro-max/data" ]; then
                rm "$SKILLS_DIR/ui-ux-pro-max/data"
                cp -r "$RESOURCES_DIR/downloaded-skills/ui-ux-pro-max-skill/src/ui-ux-pro-max/data" "$SKILLS_DIR/ui-ux-pro-max/"
            fi

            if [ -L "$SKILLS_DIR/ui-ux-pro-max/scripts" ]; then
                rm "$SKILLS_DIR/ui-ux-pro-max/scripts"
                cp -r "$RESOURCES_DIR/downloaded-skills/ui-ux-pro-max-skill/src/ui-ux-pro-max/scripts" "$SKILLS_DIR/ui-ux-pro-max/"
            fi

            print_success "ui-ux-pro-max 安装成功！"
            ;;

        superpowers)
            local source="$RESOURCES_DIR/workflows/superpowers/skills"
            if [ ! -d "$source" ]; then
                print_error "Superpowers源文件不存在: $source"
                exit 1
            fi

            print_info "正在安装 superpowers 工作流..."
            cp -r "$source"/* "$SKILLS_DIR/"
            print_success "Superpowers 工作流安装成功！"
            print_info "已安装的技能："
            ls -1 "$source" | sed 's/^/  - /'
            ;;

        *)
            print_error "未知的技能: $skill_name"
            echo "使用 './manage-skills.sh list-available' 查看可用技能"
            exit 1
            ;;
    esac
}

# 卸载技能
uninstall_skill() {
    local skill_name=$1

    if [ -z "$skill_name" ]; then
        print_error "请指定要卸载的技能名称"
        exit 1
    fi

    local skill_path="$SKILLS_DIR/$skill_name"

    if [ ! -d "$skill_path" ]; then
        print_error "技能未安装: $skill_name"
        exit 1
    fi

    print_warning "确定要卸载 $skill_name 吗？(y/N)"
    read -r response

    if [[ "$response" =~ ^[Yy]$ ]]; then
        rm -rf "$skill_path"
        print_success "$skill_name 已卸载"
    else
        print_info "取消卸载"
    fi
}

# 更新技能
update_skill() {
    local skill_name=$1

    if [ -z "$skill_name" ]; then
        print_error "请指定要更新的技能名称"
        exit 1
    fi

    print_info "正在更新 $skill_name..."

    # 先卸载
    if [ -d "$SKILLS_DIR/$skill_name" ]; then
        rm -rf "$SKILLS_DIR/$skill_name"
    fi

    # 重新安装
    install_skill "$skill_name"
}

# 显示技能信息
show_info() {
    local skill_name=$1

    if [ -z "$skill_name" ]; then
        print_error "请指定技能名称"
        exit 1
    fi

    local skill_path="$SKILLS_DIR/$skill_name"

    if [ ! -d "$skill_path" ]; then
        print_error "技能未安装: $skill_name"
        exit 1
    fi

    if [ -f "$skill_path/SKILL.md" ]; then
        print_info "技能信息: $skill_name"
        echo ""
        head -n 20 "$skill_path/SKILL.md"
    else
        print_warning "未找到技能描述文件"
    fi
}

# 主函数
main() {
    case ${1:-help} in
        list)
            list_installed
            ;;
        list-available)
            list_available
            ;;
        install)
            install_skill "$2"
            ;;
        uninstall)
            uninstall_skill "$2"
            ;;
        update)
            update_skill "$2"
            ;;
        info)
            show_info "$2"
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "未知命令: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

main "$@"
