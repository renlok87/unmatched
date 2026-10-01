#!/usr/bin/env bash
# Safe integration of a feature branch into fix/admin-panel in the main checkout.
#
# Two (or more) Claude sessions work in parallel: one in the main checkout on
# fix/admin-panel, others in git worktrees on feature branches. A merge must
# never overwrite the other session's uncommitted work, never land untested
# code on top of commits the feature branch has not seen, and never swap
# UE sources under a running editor/build of the main checkout.
#
# usage: tools/git/safe-integrate.sh <feature-branch>            # preflight only
#        tools/git/safe-integrate.sh <feature-branch> --apply    # preflight + merge
# env:   UM_MAIN_CHECKOUT (default C:/Users/ren/WebstormProjects/unmached/unmached)
#        UM_TARGET_BRANCH (default fix/admin-panel)
set -euo pipefail

BR=${1:?usage: safe-integrate.sh <feature-branch> [--apply]}
APPLY=${2:-}
MAIN=${UM_MAIN_CHECKOUT:-C:/Users/ren/WebstormProjects/unmached/unmached}
TARGET=${UM_TARGET_BRANCH:-fix/admin-panel}

fail() { echo "SAFE-INTEGRATE FAIL: $*" >&2; exit 2; }
ok() { echo "  ok  $*"; }

cd "$MAIN"
echo "SAFE-INTEGRATE $BR -> $TARGET in $MAIN"

# 1. The main checkout is on the target branch and idle in git terms.
[ "$(git branch --show-current)" = "$TARGET" ] || fail "main checkout is not on $TARGET"
GD=$(git rev-parse --git-dir)
for f in MERGE_HEAD REBASE_HEAD CHERRY_PICK_HEAD REVERT_HEAD index.lock; do
  [ -e "$GD/$f" ] && fail "git operation in progress in main checkout ($f)"
done
[ -d "$GD/rebase-merge" ] || [ -d "$GD/rebase-apply" ] && fail "rebase in progress in main checkout"
git diff --cached --quiet || fail "staged (uncommitted) changes in main checkout - the other session is mid-commit"
ok "main checkout on $TARGET, no git operation in progress, nothing staged"

# 2. The feature branch already contains every target commit, i.e. it was
#    merged with the latest target and verified (build + tests) on top of it.
git merge-base --is-ancestor "$TARGET" "$BR" ||
  fail "$BR does not contain the latest $TARGET ($(git rev-parse --short "$TARGET")): merge $TARGET into $BR, rebuild + test, then retry"
ok "$BR contains $TARGET ($(git rev-parse --short "$TARGET")) -> fast-forward"

# 3. No incoming file collides with the other session's uncommitted work.
CHANGED=$(git diff --name-only "$TARGET" "$BR")
overlap() { comm -12 <(printf '%s\n' "$1" | sed '/^$/d' | sort -u) <(printf '%s\n' "$2" | sed '/^$/d' | sort -u); }
O=$(overlap "$CHANGED" "$(git diff --name-only)")
[ -n "$O" ] && fail "incoming files have uncommitted edits in main checkout:"$'\n'"$O"
U=$(overlap "$CHANGED" "$(git ls-files --others --exclude-standard)")
[ -n "$U" ] && fail "incoming files exist as untracked files in main checkout:"$'\n'"$U"
ok "$(printf '%s\n' "$CHANGED" | sed '/^$/d' | wc -l) incoming files, none touches uncommitted/untracked work"

# 4. UE sources/config change -> nothing UE-related may run from the main checkout.
UE_CHANGED=$(printf '%s\n' "$CHANGED" | grep -E '^unreal/' || true)
if [ -n "$UE_CHANGED" ]; then
  RUNNING=$(powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { \$_.Name -match '^(UnrealEditor|UnrealEditor-Cmd|UnrealBuildTool|Unmatched)(\.exe)?\$' -and \$_.CommandLine -match 'WebstormProjects[\\\\/]unmached[\\\\/]unmached' } | ForEach-Object { '{0} {1}' -f \$_.ProcessId, \$_.Name }" | tr -d '\r')
  [ -n "$RUNNING" ] && fail "UE/UBT processes of the main checkout are running (close/finish them first):"$'\n'"$RUNNING"
  ok "no UnrealEditor/UBT/packaged client of the main checkout running"
fi

if [ "$APPLY" != "--apply" ]; then
  echo "SAFE-INTEGRATE PREFLIGHT OK (dry run; add --apply to merge)"
  exit 0
fi

BEFORE_DIRTY=$(git status --porcelain)
git merge --ff-only "$BR"
AFTER_DIRTY=$(git status --porcelain)
[ "$BEFORE_DIRTY" = "$AFTER_DIRTY" ] || echo "WARNING: working-tree status changed beyond the merge - inspect 'git status'" >&2
echo "SAFE-INTEGRATE MERGED $TARGET -> $(git rev-parse --short HEAD)"
if [ -n "$UE_CHANGED" ]; then
  echo "NOTE: UE sources changed ($(printf '%s\n' "$UE_CHANGED" | wc -l) files): rebuild UnmatchedEditor in the main checkout before opening the editor (node tools/s08/build-editor.cjs UnmatchedEditor Win64 Development -Project=$MAIN/unreal/Unmatched/Unmatched.uproject -WaitMutex -NoXGE -MaxParallelActions=6)."
fi
