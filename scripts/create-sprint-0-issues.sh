#!/usr/bin/env bash
# Sprint 0 görevlerini GitHub issue olarak toplu açar (gh CLI gerekir ve giriş yapılmış olmalı).
#
# Kullanım:
#   cp github-users.example.env github-users.env   # kullanıcı adlarını doldur
#   ./create-sprint-0-issues.sh <owner/repo>
#
# Önce denemek için: DRY_RUN=1 ./create-sprint-0-issues.sh <owner/repo>
# Bu script aynı issue'ları tekrar açar, o yüzden gerçek çalıştırmayı bir kez yap.
set -euo pipefail
cd "$(dirname "$0")"

REPO="${1:?Kullanım: ./create-sprint-0-issues.sh <owner/repo>}"
DRY_RUN="${DRY_RUN:-0}"

# GitHub kullanıcı adlarını yükle (SERHAN, LAYAN, ONURALP, MELIKE, BUSE, MUSTAFA, BATUHAN)
if [ -f github-users.env ]; then
  # shellcheck disable=SC1091
  source github-users.env
fi

# Komutu çalıştır ya da DRY_RUN ise sadece yazdır
run() {
  if [ "$DRY_RUN" = "1" ]; then
    printf '%q ' "$@"
    echo
  else
    "$@"
  fi
}

run gh label create sprint-0 --repo "$REPO" --color 4285F4 --force

while IFS=$'\t' read -r id title owner criteria; do
  # Sahibin adından değişken adını türet (Serhan -> SERHAN)
  user_var="$(echo "$owner" | tr '[:lower:]' '[:upper:]')"
  user="${!user_var:-}"

  body="$(printf '## Owner\n%s\n\n## Acceptance criteria\n%s\n\nFull list: docs/sprint-0.md\n' "$owner" "$criteria")"

  args=(issue create --repo "$REPO" --title "$id: $title" --body "$body" --label sprint-0)
  if [ -n "$user" ]; then
    args+=(--assignee "$user")
  fi
  run gh "${args[@]}"
done < sprint-0-tasks.tsv
