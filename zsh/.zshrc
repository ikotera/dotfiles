# ユーザーローカルのコマンド（rtk, uv など）
export PATH="$HOME/.local/bin:$PATH"

# Rust cargo path
source "$HOME/.cargo/env"

# VS Code Shell Integration
if [[ "$TERM_PROGRAM" == "vscode" ]]; then
    . "$(code --locate-shell-integration-path zsh)"
fi

# =================================
# ZMK Keyboard Development Settings
# =================================

# ZMK関連のエイリアス
alias zmk-build="west build"
alias zmk-flash="west flash"
alias zmk-clean="west build --pristine"
alias zmk-update="west update"

# GitHub Actions関連
alias gh-actions="gh workflow list"
alias gh-run="gh workflow run"
alias gh-logs="gh run list --limit 5"

# 便利な関数
function zmk-status() {
    echo "=== ZMK Development Status ==="
    echo "Current directory: $(pwd)"
    echo "Git branch: $(git branch --show-current)"
    echo "Git status:"
    git status --porcelain
    echo "Last commit: $(git log -1 --pretty=format:'%h %s')"
}

function zmk-commit() {
    if [ -z "$1" ]; then
        echo "Usage: zmk-commit 'commit message'"
        return 1
    fi
    git add .
    git commit -m "$1"
    git push origin main
    echo "Changes committed and pushed!"
}

function zmk-artifacts() {
    echo "Opening GitHub Actions artifacts page..."
    gh repo view --web --branch main
}

# ZMKプロジェクトディレクトリへの移動
alias cdzmk="cd ~/Github/zmk-sofle"

# VS Codeでプロジェクトを開く
alias code-zmk="code ~/Github/zmk-sofle"

# 補完の初期化
autoload -Uz compinit && compinit

# ターミナル起動時のデフォルトフォルダ（ホームで開いた場合のみ移動。VS Code 等でプロジェクト内から開いた場合は維持）
[[ -o interactive && "$PWD" == "$HOME" ]] && cd ~/Github/knowledge-base

# マシン固有・秘密の設定（API キー等）は git 管理外の ~/.zshrc.local に置く
[[ -f ~/.zshrc.local ]] && source ~/.zshrc.local
