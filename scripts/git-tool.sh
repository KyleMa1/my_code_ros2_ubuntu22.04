#!/bin/bash
#
# Git 一键管理工具
# 用法: ./git-tool.sh
#

set -eE
trap 'echo -e "\n${RED}命令执行出错，已安全停止。${NC}"; return 2>/dev/null || true' ERR

# ── 颜色定义 ─────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ── 配置 ─────────────────────────────────────────────────
REMOTE_URL="https://github.com/KyleMa1/my_code_ros2_ubuntu22.04.git"

print_header() {
    echo ""
    echo -e "${BOLD}${CYAN}========================================${NC}"
    echo -e "${BOLD}${CYAN}       Git 一键管理工具${NC}"
    echo -e "${BOLD}${CYAN}========================================${NC}"
    echo ""
}

print_menu() {
    local branch
    branch=$(git branch --show-current 2>/dev/null || echo "未初始化")
    echo -e "${BLUE}当前分支:${NC} ${GREEN}${branch}${NC}"
    echo -e "${BLUE}远程仓库:${NC} ${REMOTE_URL}"
    echo ""
    echo -e "${BOLD}── 日常操作 ──────────────────────────${NC}"
    echo -e "  ${YELLOW}1)${NC} 一键 push（add → commit → push）"
    echo -e "  ${YELLOW}2)${NC} 切换 / 新建分支"
    echo -e "  ${YELLOW}3)${NC} 拉取远程更新（pull）"
    echo ""
    echo -e "${BOLD}── 查看差分 ──────────────────────────${NC}"
    echo -e "  ${YELLOW}4)${NC} 查看当前改动（工作区 diff）"
    echo -e "  ${YELLOW}5)${NC} 查看暂存区改动（staged diff）"
    echo -e "  ${YELLOW}6)${NC} 查看提交历史"
    echo -e "  ${YELLOW}7)${NC} 对比两个提交 / 分支的差异"
    echo ""
    echo -e "${BOLD}── 回退操作 ──────────────────────────${NC}"
    echo -e "  ${YELLOW}8)${NC} 撤销工作区改动（还原文件）"
    echo -e "  ${YELLOW}9)${NC} 软回退到某个提交（保留改动）"
    echo -e "  ${YELLOW}10)${NC} 硬回退到某个提交（丢弃改动）"
    echo -e "  ${YELLOW}11)${NC} 回滚某次提交（生成反向提交）"
    echo ""
    echo -e "${BOLD}── 其他 ──────────────────────────────${NC}"
    echo -e "  ${YELLOW}12)${NC} 查看仓库状态"
    echo -e "  ${YELLOW}13)${NC} stash 暂存当前改动"
    echo -e "  ${YELLOW}14)${NC} stash 恢复暂存改动"
    echo -e "  ${YELLOW}0)${NC}  退出"
    echo ""
}

check_disk_space() {
    local avail_kb
    avail_kb=$(df --output=avail . | tail -1 | tr -d ' ')
    if [ "${avail_kb}" -lt 1048576 ]; then
        echo -e "${RED}警告: 磁盘剩余空间不足 1GB ($(( avail_kb / 1024 ))MB)!${NC}"
        echo -e "${YELLOW}建议先清理空间: make clean 或 rm -rf build/ install/ log/${NC}"
        read -rp "$(echo -e "${YELLOW}是否继续? [y/N]: ${NC}")" yn
        if [[ ! "${yn}" =~ ^[Yy]$ ]]; then
            return 1
        fi
    fi
}

ensure_git_repo() {
    if [ ! -d ".git" ]; then
        echo -e "${YELLOW}当前目录未初始化 Git 仓库，正在初始化...${NC}"
        git init
        git remote add origin "${REMOTE_URL}" 2>/dev/null || true

        if [ ! -f ".gitignore" ]; then
            echo -e "${RED}.gitignore 不存在，请先创建！${NC}"
            return 1
        fi

        echo -e "${GREEN}Git 仓库已初始化，远程地址: ${REMOTE_URL}${NC}"
    fi

    local current_remote
    current_remote=$(git remote get-url origin 2>/dev/null || echo "")
    if [ -z "${current_remote}" ]; then
        git remote add origin "${REMOTE_URL}"
    fi
}

# ── 1) 一键 push ────────────────────────────────────────
do_push() {
    echo -e "\n${BOLD}── 一键 Push ──${NC}\n"

    echo -e "${BLUE}当前改动:${NC}"
    git status --short
    echo ""

    if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
        echo -e "${YELLOW}没有任何改动，无需提交。${NC}"
        return
    fi

    local branches
    branches=$(git branch -a 2>/dev/null | sed 's/^[* ]*//' | sed 's/remotes\/origin\///' | sort -u)
    local current
    current=$(git branch --show-current 2>/dev/null || echo "main")

    echo -e "${BLUE}可用分支:${NC}"
    echo "${branches}" | head -20
    echo ""
    read -rp "$(echo -e "${CYAN}推送到哪个分支? [${current}]: ${NC}")" target_branch
    target_branch=${target_branch:-${current}}

    if [ "${target_branch}" != "${current}" ]; then
        if git show-ref --verify --quiet "refs/heads/${target_branch}"; then
            git checkout "${target_branch}"
        else
            git checkout -b "${target_branch}"
        fi
    fi

    read -rp "$(echo -e "${CYAN}提交信息: ${NC}")" commit_msg
    if [ -z "${commit_msg}" ]; then
        commit_msg="update $(date '+%Y-%m-%d %H:%M:%S')"
    fi

    echo ""
    echo -e "${BLUE}即将执行:${NC}"
    echo -e "  git add -A"
    echo -e "  git commit -m \"${commit_msg}\""
    echo -e "  git push origin ${target_branch}"
    echo ""
    read -rp "$(echo -e "${YELLOW}确认? [Y/n]: ${NC}")" confirm
    confirm=${confirm:-Y}

    if [[ "${confirm}" =~ ^[Yy]$ ]]; then
        check_disk_space || return
        echo -e "${BLUE}正在添加文件...${NC}"
        git add -A
        local file_count
        file_count=$(git diff --cached --stat | tail -1 | grep -oP '\d+ file' | grep -oP '\d+' || echo "0")
        echo -e "${BLUE}暂存了 ${file_count} 个文件的改动${NC}"
        git commit -m "${commit_msg}"
        echo -e "${BLUE}正在推送到 origin/${target_branch}...${NC}"
        git push -u origin "${target_branch}"
        echo -e "\n${GREEN}推送成功！${NC}"
    else
        echo -e "${RED}已取消。${NC}"
    fi
}

# ── 2) 切换 / 新建分支 ──────────────────────────────────
do_switch_branch() {
    echo -e "\n${BOLD}── 切换 / 新建分支 ──${NC}\n"

    echo -e "${BLUE}本地分支:${NC}"
    git branch
    echo ""
    echo -e "${BLUE}远程分支:${NC}"
    git branch -r 2>/dev/null || echo "  (无远程分支)"
    echo ""

    read -rp "$(echo -e "${CYAN}输入分支名（不存在则新建）: ${NC}")" branch_name
    if [ -z "${branch_name}" ]; then
        echo -e "${RED}分支名不能为空。${NC}"
        return
    fi

    if git show-ref --verify --quiet "refs/heads/${branch_name}"; then
        git checkout "${branch_name}"
        echo -e "${GREEN}已切换到分支: ${branch_name}${NC}"
    else
        read -rp "$(echo -e "${YELLOW}分支 '${branch_name}' 不存在，是否新建? [Y/n]: ${NC}")" yn
        yn=${yn:-Y}
        if [[ "${yn}" =~ ^[Yy]$ ]]; then
            git checkout -b "${branch_name}"
            echo -e "${GREEN}已创建并切换到新分支: ${branch_name}${NC}"
        fi
    fi
}

# ── 3) pull ──────────────────────────────────────────────
do_pull() {
    echo -e "\n${BOLD}── 拉取远程更新 ──${NC}\n"
    local current
    current=$(git branch --show-current)
    echo -e "${BLUE}从 origin/${current} 拉取...${NC}"
    git pull origin "${current}"
    echo -e "${GREEN}拉取完成。${NC}"
}

# ── 4) 工作区 diff ──────────────────────────────────────
do_diff() {
    echo -e "\n${BOLD}── 工作区改动 (未暂存) ──${NC}\n"
    if git diff --quiet; then
        echo -e "${YELLOW}没有未暂存的改动。${NC}"
    else
        git diff --stat
        echo ""
        read -rp "$(echo -e "${CYAN}查看详细 diff? [Y/n]: ${NC}")" yn
        yn=${yn:-Y}
        if [[ "${yn}" =~ ^[Yy]$ ]]; then
            git diff --color | less -R
        fi
    fi
}

# ── 5) 暂存区 diff ──────────────────────────────────────
do_diff_staged() {
    echo -e "\n${BOLD}── 暂存区改动 (已 add) ──${NC}\n"
    if git diff --cached --quiet; then
        echo -e "${YELLOW}暂存区没有改动。${NC}"
    else
        git diff --cached --stat
        echo ""
        read -rp "$(echo -e "${CYAN}查看详细 diff? [Y/n]: ${NC}")" yn
        yn=${yn:-Y}
        if [[ "${yn}" =~ ^[Yy]$ ]]; then
            git diff --cached --color | less -R
        fi
    fi
}

# ── 6) 提交历史 ─────────────────────────────────────────
do_log() {
    echo -e "\n${BOLD}── 提交历史 ──${NC}\n"
    read -rp "$(echo -e "${CYAN}显示最近几条? [20]: ${NC}")" count
    count=${count:-20}
    git log --oneline --graph --decorate --all -n "${count}"
}

# ── 7) 对比两个提交/分支 ────────────────────────────────
do_diff_commits() {
    echo -e "\n${BOLD}── 对比两个提交 / 分支 ──${NC}\n"

    echo -e "${BLUE}最近的提交:${NC}"
    git log --oneline -10
    echo ""

    read -rp "$(echo -e "${CYAN}起始 (commit hash / 分支名): ${NC}")" from_ref
    read -rp "$(echo -e "${CYAN}目标 (commit hash / 分支名) [HEAD]: ${NC}")" to_ref
    to_ref=${to_ref:-HEAD}

    echo ""
    echo -e "${BLUE}${from_ref} → ${to_ref} 的改动:${NC}"
    git diff --stat "${from_ref}" "${to_ref}"
    echo ""
    read -rp "$(echo -e "${CYAN}查看详细 diff? [Y/n]: ${NC}")" yn
    yn=${yn:-Y}
    if [[ "${yn}" =~ ^[Yy]$ ]]; then
        git diff --color "${from_ref}" "${to_ref}" | less -R
    fi
}

# ── 8) 撤销工作区改动 ───────────────────────────────────
do_restore() {
    echo -e "\n${BOLD}── 撤销工作区改动 ──${NC}\n"

    echo -e "${BLUE}已修改的文件:${NC}"
    git diff --name-only
    echo ""

    echo -e "  ${YELLOW}1)${NC} 还原单个文件"
    echo -e "  ${YELLOW}2)${NC} 还原所有改动"
    read -rp "$(echo -e "${CYAN}选择: ${NC}")" choice

    case ${choice} in
        1)
            read -rp "$(echo -e "${CYAN}文件路径: ${NC}")" filepath
            git checkout -- "${filepath}"
            echo -e "${GREEN}已还原: ${filepath}${NC}"
            ;;
        2)
            read -rp "$(echo -e "${RED}确认还原所有未暂存改动? 不可恢复! [y/N]: ${NC}")" yn
            if [[ "${yn}" =~ ^[Yy]$ ]]; then
                git checkout -- .
                echo -e "${GREEN}所有改动已还原。${NC}"
            else
                echo -e "${YELLOW}已取消。${NC}"
            fi
            ;;
        *)
            echo -e "${RED}无效选择。${NC}"
            ;;
    esac
}

# ── 9) 软回退 ───────────────────────────────────────────
do_soft_reset() {
    echo -e "\n${BOLD}── 软回退（保留改动到工作区）──${NC}\n"

    echo -e "${BLUE}最近的提交:${NC}"
    git log --oneline -10
    echo ""

    read -rp "$(echo -e "${CYAN}回退到哪个提交 (hash): ${NC}")" target_hash
    if [ -z "${target_hash}" ]; then
        echo -e "${RED}未输入提交 hash。${NC}"
        return
    fi

    echo -e "${YELLOW}将回退到 ${target_hash}，之后的改动保留在工作区。${NC}"
    read -rp "$(echo -e "${YELLOW}确认? [y/N]: ${NC}")" yn
    if [[ "${yn}" =~ ^[Yy]$ ]]; then
        git reset --soft "${target_hash}"
        echo -e "${GREEN}软回退完成。改动已保留在暂存区。${NC}"
        git status --short
    else
        echo -e "${YELLOW}已取消。${NC}"
    fi
}

# ── 10) 硬回退 ──────────────────────────────────────────
do_hard_reset() {
    echo -e "\n${BOLD}── 硬回退（丢弃所有改动）──${NC}\n"

    echo -e "${BLUE}最近的提交:${NC}"
    git log --oneline -10
    echo ""

    read -rp "$(echo -e "${CYAN}回退到哪个提交 (hash): ${NC}")" target_hash
    if [ -z "${target_hash}" ]; then
        echo -e "${RED}未输入提交 hash。${NC}"
        return
    fi

    echo ""
    echo -e "${RED}${BOLD}警告: 硬回退将永久丢弃 ${target_hash} 之后的所有改动！${NC}"
    echo -e "${RED}此操作不可撤销！${NC}"
    read -rp "$(echo -e "${RED}输入 'YES' 确认: ${NC}")" confirm
    if [ "${confirm}" = "YES" ]; then
        git reset --hard "${target_hash}"
        echo -e "${GREEN}硬回退完成。当前 HEAD:${NC}"
        git log --oneline -1
    else
        echo -e "${YELLOW}已取消。${NC}"
    fi
}

# ── 11) revert ──────────────────────────────────────────
do_revert() {
    echo -e "\n${BOLD}── 回滚提交（生成反向提交，安全）──${NC}\n"

    echo -e "${BLUE}最近的提交:${NC}"
    git log --oneline -10
    echo ""

    read -rp "$(echo -e "${CYAN}要回滚哪个提交 (hash): ${NC}")" target_hash
    if [ -z "${target_hash}" ]; then
        echo -e "${RED}未输入提交 hash。${NC}"
        return
    fi

    echo -e "${YELLOW}将生成一个反向提交来撤销 ${target_hash} 的改动。${NC}"
    echo -e "${GREEN}这是最安全的回退方式，不会改写历史。${NC}"
    read -rp "$(echo -e "${CYAN}确认? [Y/n]: ${NC}")" yn
    yn=${yn:-Y}
    if [[ "${yn}" =~ ^[Yy]$ ]]; then
        git revert "${target_hash}"
        echo -e "${GREEN}回滚完成。${NC}"
    else
        echo -e "${YELLOW}已取消。${NC}"
    fi
}

# ── 12) status ──────────────────────────────────────────
do_status() {
    echo -e "\n${BOLD}── 仓库状态 ──${NC}\n"
    git status
    echo ""
    echo -e "${BLUE}本地分支:${NC}"
    git branch -vv
}

# ── 13) stash 暂存 ──────────────────────────────────────
do_stash_save() {
    echo -e "\n${BOLD}── Stash 暂存改动 ──${NC}\n"
    read -rp "$(echo -e "${CYAN}暂存备注 [可选]: ${NC}")" msg
    if [ -n "${msg}" ]; then
        git stash push -m "${msg}"
    else
        git stash push
    fi
    echo -e "${GREEN}改动已暂存。${NC}"
    echo -e "${BLUE}当前 stash 列表:${NC}"
    git stash list
}

# ── 14) stash 恢复 ──────────────────────────────────────
do_stash_pop() {
    echo -e "\n${BOLD}── Stash 恢复改动 ──${NC}\n"

    local stash_list
    stash_list=$(git stash list 2>/dev/null)
    if [ -z "${stash_list}" ]; then
        echo -e "${YELLOW}没有暂存的改动。${NC}"
        return
    fi

    echo -e "${BLUE}暂存列表:${NC}"
    echo "${stash_list}"
    echo ""
    read -rp "$(echo -e "${CYAN}恢复哪个? [0]: ${NC}")" idx
    idx=${idx:-0}
    git stash pop "stash@{${idx}}"
    echo -e "${GREEN}改动已恢复。${NC}"
}

# ── 主循环 ───────────────────────────────────────────────
main() {
    ensure_git_repo || exit 1
    check_disk_space || true
    while true; do
        print_header
        print_menu
        read -rp "$(echo -e "${BOLD}请选择 [0-14]: ${NC}")" choice
        case ${choice} in
            1)  do_push ;;
            2)  do_switch_branch ;;
            3)  do_pull ;;
            4)  do_diff ;;
            5)  do_diff_staged ;;
            6)  do_log ;;
            7)  do_diff_commits ;;
            8)  do_restore ;;
            9)  do_soft_reset ;;
            10) do_hard_reset ;;
            11) do_revert ;;
            12) do_status ;;
            13) do_stash_save ;;
            14) do_stash_pop ;;
            0)  echo -e "${GREEN}再见！${NC}"; exit 0 ;;
            *)  echo -e "${RED}无效选择，请重试。${NC}" ;;
        esac
        echo ""
        read -rp "$(echo -e "${CYAN}按回车继续...${NC}")"
    done
}

main "$@"
