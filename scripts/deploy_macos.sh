#!/usr/bin/env bash
# 把 macOS 原生面板编译、自签、上墙。对应 Windows 侧的 deploy_skin.ps1。
#
# 只需 Command Line Tools（xcode-select --install），**不需要 Xcode、不需要 Apple 账号**：
# 自己在自己机器上编出来的 App 没有隔离标记，Gatekeeper 不拦。
#
# 用法：
#   bash scripts/deploy_macos.sh --board ~/Deskdash [--level icon|desktop|back] [--source <Panel.swift>]
#   bash scripts/deploy_macos.sh --board ~/Deskdash --stop        # 只停掉，不重编
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(dirname "$HERE")"
BOARD=""
LEVEL="icon"
SOURCE="$SKILL_ROOT/templates/macos-panel/Panel.swift"
APP_NAME="DeskdashPanel"
STOP_ONLY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --board)  BOARD="$2"; shift 2 ;;
    --level)  LEVEL="$2"; shift 2 ;;
    --source) SOURCE="$2"; shift 2 ;;
    --name)   APP_NAME="$2"; shift 2 ;;
    --stop)   STOP_ONLY=1; shift ;;
    *) echo "未知参数：$1" >&2; exit 2 ;;
  esac
done

if [ -z "$BOARD" ]; then echo "缺 --board <板目录>" >&2; exit 2; fi
BOARD="${BOARD/#\~/$HOME}"

pkill -f "$APP_NAME" 2>/dev/null || true
if [ "$STOP_ONLY" = "1" ]; then echo "已停掉 $APP_NAME"; exit 0; fi

# —— 前置检查：把「没装工具链」和「代码有错」分开报，别让用户对着编译错误猜 ——
if ! command -v swiftc >/dev/null 2>&1; then
  echo "找不到 swiftc。先装 Command Line Tools：xcode-select --install" >&2
  exit 3
fi
if [ ! -f "$SOURCE" ]; then echo "找不到面板源码：$SOURCE" >&2; exit 3; fi
if [ ! -f "$BOARD/data.json" ]; then
  echo "提示：$BOARD/data.json 还不存在 —— 面板会显示「读不到数据」。" >&2
  echo "      先跑一次：python3 $SKILL_ROOT/scripts/orchestrator.py --board $BOARD" >&2
fi

APP="$BOARD/$APP_NAME.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>$APP_NAME</string>
  <key>CFBundleExecutable</key><string>$APP_NAME</string>
  <key>CFBundleIdentifier</key><string>local.deskdash.panel</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSUIElement</key><true/>
  <key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST

echo "编译 $(basename "$SOURCE") …"
swiftc -O "$SOURCE" -o "$APP/Contents/MacOS/$APP_NAME"

echo "本机自签（无需任何证书或账号）…"
codesign --force --deep --sign - "$APP" >/dev/null

# 🔴 变量名后面紧跟中文时必须写 ${VAR}：某些 locale 下 bash 会把多字节字符的首字节
# 当成变量名的一部分，于是 set -u 报「未绑定的变量」——错在标点，不在逻辑。
echo "上墙（层级 ${LEVEL}）…"
open "$APP" --args --board "$BOARD" --level "$LEVEL"
sleep 2

PID="$(pgrep -f "$APP_NAME" | head -1 || true)"
if [ -z "$PID" ]; then
  echo "🔴 进程没起来。手动跑一次看报错：" >&2
  echo "   \"$APP/Contents/MacOS/$APP_NAME\" --board \"$BOARD\" --level $LEVEL" >&2
  exit 4
fi

echo "已上墙：PID $PID"
# 内存看 phys_footprint，不看 RSS —— 后者把共享框架也算进去，会明显偏大
footprint -p "$PID" 2>/dev/null | grep -m1 phys_footprint: | sed 's/^/  /' || true
echo
echo "拖不动 / 点不了 → 换层级重跑：--level back（一定可交互，代价是它成为一个真窗口）"
echo "停掉         → bash scripts/deploy_macos.sh --board \"$BOARD\" --stop"
