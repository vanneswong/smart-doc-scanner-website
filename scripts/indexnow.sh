#!/usr/bin/env bash
#
# IndexNow 自动提交脚本
#
# 用法:
#   ./scripts/indexnow.sh                     # 读取 sitemap.xml，自动批量提交同域 URL
#   ./scripts/indexnow.sh --dry-run           # 只打印将要提交的内容，不发送请求
#   ./scripts/indexnow.sh --url <URL>         # 单条提交
#   ./scripts/indexnow.sh --single --url <URL>  # 单条提交（GET，key location 作为 URL 参数）
#   ./scripts/indexnow.sh --url <URL1> --url <URL2>   # 多条批量提交
#   ./scripts/indexnow.sh --changed-only      # 只提交 git 本次改动涉及到的页面
#
# 可选参数:
#   --host <HOST>        指定要提交的域名（默认从密钥文件/sitemap 推断，或 smartscanner.zynotes.cn）
#   --key <KEY>          指定 IndexNow 密钥（默认自动查找仓库根目录的 32 位十六进制 txt 文件）
#   --endpoint <URL>     可重复，指定提交端点（默认 api.indexnow.org + www.bing.com）
#   --quiet              简要输出
#
# 依赖: curl、python3（仅用标准库）
# 退出码: 0 全部成功；1 有端点失败；2 配置/参数错误

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITEMAP="$REPO_ROOT/sitemap.xml"

HOST="${INDEXNOW_HOST:-}"
KEY="${INDEXNOW_KEY:-}"
DRY_RUN=0
CHANGED_ONLY=0
QUIET=0
SINGLE=0
declare -a EXTRA_URLS=()
declare -a ENDPOINTS=()

DEFAULT_ENDPOINTS=(
  "https://api.indexnow.org/indexnow"
  "https://www.bing.com/indexnow"
)

# ---------------------------------------------------------------- 参数解析
need_value() {
  if [[ $# -lt 2 || -z "${2:-}" ]]; then
    echo "错误: 参数 $1 需要一个值" >&2
    exit 2
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --url)
      need_value "$@"; EXTRA_URLS+=("$2"); shift 2 ;;
    --host)
      need_value "$@"; HOST="$2"; shift 2 ;;
    --key)
      need_value "$@"; KEY="$2"; shift 2 ;;
    --endpoint)
      need_value "$@"; ENDPOINTS+=("$2"); shift 2 ;;
    --sitemap)
      need_value "$@"; SITEMAP="$2"; shift 2 ;;
    --dry-run)
      DRY_RUN=1; shift ;;
    --single)
      SINGLE=1; shift ;;
    --changed-only)
      CHANGED_ONLY=1; shift ;;
    --quiet)
      QUIET=1; shift ;;
    -h|--help)
      sed -n '2,19p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)
      echo "错误: 未知参数 $1" >&2; exit 2 ;;
  esac
done

if [[ ${#ENDPOINTS[@]} -eq 0 ]]; then
  ENDPOINTS=("${DEFAULT_ENDPOINTS[@]}")
fi

# ---------------------------------------------------------------- 查找密钥
# 规则: 仓库根目录下 32 位十六进制命名的 .txt 文件即 IndexNow 密钥文件
find_key() {
  local f base content
  for f in "$REPO_ROOT"/*.txt; do
    [[ -e "$f" ]] || continue
    base="$(basename "$f" .txt)"
    if [[ "$base" =~ ^[0-9a-fA-F]{32}$ ]]; then
      content="$(tr -d ' \t\r\n' < "$f")"
      # 文件内容应与文件名一致（IndexNow 校验要求）
      if [[ "$content" == "$base" ]]; then
        printf '%s' "$base"
        return 0
      fi
    fi
  done
  return 1
}

if [[ -z "$KEY" ]]; then
  if ! KEY="$(find_key)"; then
    echo "错误: 未找到 IndexNow 密钥文件（仓库根目录下 32 位十六进制命名、内容同名的 .txt）" >&2
    echo "      可用 --key <KEY> 或环境变量 INDEXNOW_KEY 指定" >&2
    exit 2
  fi
fi

if [[ ! "$KEY" =~ ^[0-9a-fA-F]{32}$ ]]; then
  echo "错误: 密钥格式不合法（应为 32 位十六进制）: $KEY" >&2
  exit 2
fi

# ---------------------------------------------------------------- 推断域名
if [[ -z "$HOST" ]]; then
  if [[ -f "$SITEMAP" ]]; then
    HOST="$(python3 - "$SITEMAP" <<'PY'
import sys, urllib.parse
import xml.etree.ElementTree as ET
try:
    root = ET.parse(sys.argv[1]).getroot()
except Exception:
    sys.exit(0)
for el in root.iter():
    if el.tag.endswith('loc') and el.text:
        print(urllib.parse.urlsplit(el.text.strip()).netloc)
        break
PY
)"
  fi
fi

if [[ -z "$HOST" ]]; then
  echo "错误: 无法推断域名，请用 --host 指定（例如 --host example.com）" >&2
  exit 2
fi

# ---------------------------------------------------------------- 收集 URL
collect_urls() {
  # 1) sitemap 中同域 URL（显式传入 --url 或 --changed-only 时不再自动加入 sitemap）
  if [[ ${#EXTRA_URLS[@]} -eq 0 && "$CHANGED_ONLY" -eq 0 && -f "$SITEMAP" ]]; then
    python3 - "$SITEMAP" "$HOST" <<'PY'
import sys, urllib.parse
import xml.etree.ElementTree as ET
sitemap, host = sys.argv[1], sys.argv[2]
root = ET.parse(sitemap).getroot()
seen = set()
for el in root.iter():
    if not el.tag.endswith('loc') or not el.text:
        continue
    url = el.text.strip()
    parts = urllib.parse.urlsplit(url)
    if parts.netloc != host:
        continue
    if parts.path.endswith('/404.html'):
        continue
    if url in seen:
        continue
    seen.add(url)
    print(url)
PY
  fi

  # 2) 命令行显式指定的 URL（同域校验）
  local u
  for u in ${EXTRA_URLS+"${EXTRA_URLS[@]}"}; do
    python3 - "$u" "$HOST" <<'PY' && true
import sys, urllib.parse
url, host = sys.argv[1], sys.argv[2]
if urllib.parse.urlsplit(url).netloc != host:
    sys.exit(1)
print(url)
PY
    if [[ $? -ne 0 ]]; then
      echo "警告: 跳过非同域 URL: $u（IndexNow 要求同一次提交的 URL 同属 $HOST）" >&2
    fi
  done

  # 3) 仅提交 git 改动涉及的页面
  if [[ "$CHANGED_ONLY" -eq 1 ]]; then
    local f
    if git -C "$REPO_ROOT" rev-parse --git-dir >/dev/null 2>&1; then
      for f in $(git -C "$REPO_ROOT" diff --name-only HEAD~1 HEAD 2>/dev/null; \
                 git -C "$REPO_ROOT" diff --name-only 2>/dev/null; \
                 git -C "$REPO_ROOT" diff --name-only --cached 2>/dev/null); do
        case "$f" in
          *.html)
            [[ "$(basename "$f")" == "404.html" ]] && continue
            printf 'https://%s/%s\n' "$HOST" "$f"
            ;;
        esac
      done
    fi
  fi
}

mapfile -t URLS < <(collect_urls | grep -v '^[[:space:]]*$' | awk '!seen[$0]++')

if [[ ${#URLS[@]} -eq 0 ]]; then
  echo "没有需要提交的 URL。" >&2
  exit 0
fi

KEY_LOCATION="https://$HOST/$KEY.txt"

# ---------------------------------------------------------------- 构造载荷
PAYLOAD="$(python3 - "$HOST" "$KEY" "$KEY_LOCATION" "${URLS[@]}" <<'PY'
import json, sys
host, key, key_location = sys.argv[1], sys.argv[2], sys.argv[3]
urls = sys.argv[4:]
print(json.dumps({
    "host": host,
    "key": key,
    "keyLocation": key_location,
    "urlList": urls,
}, ensure_ascii=False, indent=2))
PY
)"

if [[ "$SINGLE" -eq 1 && ${#URLS[@]} -ne 1 ]]; then
  echo "错误: --single 模式要求恰好 1 条 URL（当前 ${#URLS[@]} 条）" >&2
  exit 2
fi

# ---------------------------------------------------------------- GET 单条提交
if [[ "$SINGLE" -eq 1 ]]; then
  target="${URLS[0]}"
  encoded_url="$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1], safe=""))' "$target")"
  encoded_loc="$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1], safe=""))' "$KEY_LOCATION")"
  FAILED=0
  for ep in "${ENDPOINTS[@]}"; do
    req="$ep?url=$encoded_url&key=$KEY&keyLocation=$encoded_loc"
    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "GET $req"
      continue
    fi
    code="$(curl -sS -o /dev/null -w '%{http_code}' "$req" --max-time 30 2>/dev/null)"
    if [[ "$code" == "200" || "$code" == "202" ]]; then
      printf '  %-42s HTTP %-3s %s\n' "$ep" "$code" "提交成功"
    else
      printf '  %-42s HTTP %-3s %s\n' "$ep" "${code:-ERR}" "提交失败" >&2
      FAILED=1
    fi
  done
  if [[ "$DRY_RUN" -eq 1 ]]; then
    exit 0
  fi
  if [[ "$FAILED" -eq 0 ]]; then
    echo "完成：GET 单条提交 $target"
    exit 0
  fi
  exit 1
fi

if [[ "$QUIET" -eq 0 || "$DRY_RUN" -eq 1 ]]; then
  echo "域名:        $HOST"
  echo "密钥位置:    $KEY_LOCATION"
  echo "待提交 URL:  ${#URLS[@]} 条"
  local_i=0
  for u in "${URLS[@]}"; do
    local_i=$((local_i + 1))
    echo "  $local_i) $u"
  done
  echo
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "--- dry-run，请求体如下 ---"
  echo "$PAYLOAD"
  exit 0
fi

# ---------------------------------------------------------------- POST 批量提交
FAILED=0
for ep in "${ENDPOINTS[@]}"; do
  code="$(curl -sS -o /tmp/indexnow-resp.$$ -w '%{http_code}' \
    -X POST "$ep" \
    -H 'Content-Type: application/json; charset=utf-8' \
    --data-binary "$PAYLOAD" \
    --max-time 30 2>/dev/null)"

  case "$code" in
    200) msg="提交成功（密钥校验通过）" ;;
    202) msg="已接受（密钥校验进行中）" ;;
    400) msg="请求格式错误" ;;
    403) msg="密钥无效（文件内容与 key 不一致）" ;;
    422) msg="URL 与 host 不匹配，或密钥文件不可访问" ;;
    429) msg="请求过于频繁（限流）" ;;
    "")  msg="网络错误或超时" ;;
    *)   msg="未预期的状态码" ;;
  esac

  if [[ "$code" == "200" || "$code" == "202" ]]; then
    printf '  %-42s HTTP %-3s %s\n' "$ep" "$code" "$msg"
  else
    printf '  %-42s HTTP %-3s %s\n' "$ep" "${code:-ERR}" "$msg" >&2
    FAILED=1
  fi
done

rm -f /tmp/indexnow-resp.$$

if [[ "$FAILED" -eq 0 ]]; then
  echo "完成：已向 ${#ENDPOINTS[@]} 个端点提交 ${#URLS[@]} 条 URL。"
  exit 0
fi

echo "有端点提交失败，请检查上面的状态码说明。" >&2
exit 1
