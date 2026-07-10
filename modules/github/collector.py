# modules/github/collector.py — GitHub 仓库动态:某用户的公开仓 star / 语言 / 最近更新 + 总 star / 开放 PR 数。
#
# 契约:`python collector.py --config <config.json>`,stdout 单行 JSON;成功=扁平 outputs,失败=err。
# 自包含 stdlib(subprocess 调 gh CLI / urllib 走 REST);无第三方依赖(deps: [])。无 eval/exec/shell=True。
#
# 数据源(双档,自动降级):
#   ① gh CLI(优先)—— 复用本机 `gh` 已登录的认证,配额高、可读私有(本模块只取公开)。存在性检查失败即降级。
#   ② REST 匿名(降级)—— 无 gh 时直连 api.github.com。⚠ 匿名限流:核心 60 次/小时、search 10 次/分钟;
#      个人用足够,批量/多板会更快触顶(触顶 → 返回 rate_limit 错误,agent 据此提示装 gh 或稍后重试)。
#
# 脱敏:用户名进 config(示例 octocat);无任何硬编码账号。仅访问 api.github.com(privacy.network 已声明)。
import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

MAX_REPOS = 5                                       # band.inc 固定 5 行,超出截断
_API = "https://api.github.com"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# 常见语言 → 状态点色(近 GitHub 官方色);未知 → 中性灰。
_LANG_COLOR = {
    "python": "53,114,165,255", "javascript": "241,224,90,255", "typescript": "49,120,198,255",
    "go": "0,173,216,255", "rust": "222,165,132,255", "java": "176,114,25,255",
    "c": "85,85,85,255", "c++": "243,75,125,255", "c#": "23,134,0,255",
    "shell": "137,224,81,255", "html": "227,76,38,255", "css": "86,61,124,255",
    "ruby": "112,21,22,255", "php": "79,93,149,255", "swift": "240,81,56,255",
    "kotlin": "169,123,255,255", "dart": "0,180,148,255", "vue": "65,184,131,255",
    "jupyter notebook": "218,121,44,255", "lua": "0,0,128,255", "scala": "194,45,64,255",
}
_LANG_UNKNOWN = "120,130,145,255"


class _NetError(Exception):
    """网络/HTTP 层失败。"""


class _RateLimit(Exception):
    """API 限流(REST 匿名触顶)。"""


def _err(kind, retryable, hint):
    return {"ok": False, "err": {"kind": kind, "retryable": bool(retryable),
                                 "hint_for_agent": str(hint)}}


def _emit(obj):
    b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    sys.stdout.buffer.write(b + b"\n")
    try:
        sys.stdout.buffer.flush()
    except OSError:
        pass


def load_config(path):
    cfg = {"username": "", "max_repos": MAX_REPOS, "include_forks": False, "use_gh_cli": True}
    if path and os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except (OSError, ValueError):
            pass
    return cfg


# —— 纯逻辑(离线可测)——

def lang_color(language):
    """语言名 → 状态点色(r,g,b,a);未知/空 → 中性灰。"""
    return _LANG_COLOR.get(str(language or "").strip().lower(), _LANG_UNKNOWN)


def activity_label(pushed_at, now):
    """ISO8601 UTC(如 2026-07-08T05:15:21Z)→ 相对时间中文;空/解析失败 → 空串。"""
    if not pushed_at:
        return ""
    try:
        dt = datetime.fromisoformat(str(pushed_at).replace("Z", "+00:00"))
    except ValueError:
        return ""
    if dt.tzinfo is None:                            # 无时区(理论上 API 总带 Z;防御:按 UTC 处理)
        dt = dt.replace(tzinfo=timezone.utc)
    days = (now - dt).days
    if days <= 0:
        return "今天更新"
    if days == 1:
        return "昨天更新"
    if days < 30:
        return "%d天前更新" % days
    if days < 365:
        return "%d个月前更新" % (days // 30)
    return "%d年前更新" % (days // 365)


def filter_repos(repos, username, include_forks):
    """规范化 repo 列表 → 过滤(公开 + 可选去 fork + 排除 profile 仓)→ 按 pushed 降序。
    repos 元素为统一结构 dict(见 _norm_gh/_norm_rest)。"""
    out = []
    for r in repos:
        if r.get("is_private"):
            continue
        if not include_forks and r.get("is_fork"):
            continue
        if username and r.get("name") == username:       # GitHub profile README 仓(名==用户名)排除
            continue
        out.append(r)
    out.sort(key=lambda r: str(r.get("pushed_at") or ""), reverse=True)
    return out


# —— gh CLI 档 ——

def _gh_available():
    return shutil.which("gh") is not None


def _gh_json(args, timeout=20):
    kw = {"capture_output": True, "text": True, "encoding": "utf-8", "timeout": timeout}
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        r = subprocess.run(["gh"] + args, **kw)       # noqa: S603 (list 参数,非 shell)
    except (OSError, subprocess.TimeoutExpired):
        raise _NetError("gh 调用失败/超时")
    if r.returncode != 0:
        raise _NetError("gh 非零退出")                 # 未登录/网络问题都归网络类;不回显 stderr(可能含 token)
    try:
        return json.loads(r.stdout or "null")
    except ValueError:
        raise _NetError("gh 输出非 JSON")


def _norm_gh(raw):
    return {"name": raw.get("name", ""), "is_fork": bool(raw.get("isFork")),
            "is_private": bool(raw.get("isPrivate")), "pushed_at": raw.get("pushedAt", ""),
            "stars": raw.get("stargazerCount", 0) or 0, "url": raw.get("url", ""),
            "language": (raw.get("primaryLanguage") or {}).get("name")}


def _fetch_gh(username, want):
    raw = _gh_json(["repo", "list", username, "--json",
                    "name,isFork,isPrivate,pushedAt,stargazerCount,url,primaryLanguage",
                    "--limit", "100"])
    repos = [_norm_gh(r) for r in (raw or [])]
    pr_total = _open_pr_total_gh(username)
    return repos, pr_total


def _open_pr_total_gh(username):
    """开放 PR 总数(best-effort):gh api search/issues 取 total_count;失败 → -1。"""
    try:
        j = _gh_json(["api", "-X", "GET", "search/issues",
                      "-f", "q=is:pr is:open author:%s" % username], timeout=15)
        return int(j.get("total_count", -1))
    except (_NetError, ValueError, TypeError, AttributeError):
        return -1


# —— REST 匿名档 ——

def _rest_json(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": _UA,
                                               "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            raise _RateLimit("REST 匿名限流(%d)" % e.code)
        raise _NetError("HTTP %d" % e.code)
    except Exception:
        raise _NetError("REST 请求失败")


def _norm_rest(raw):
    return {"name": raw.get("name", ""), "is_fork": bool(raw.get("fork")),
            "is_private": bool(raw.get("private")), "pushed_at": raw.get("pushed_at", ""),
            "stars": raw.get("stargazers_count", 0) or 0, "url": raw.get("html_url", ""),
            "language": raw.get("language")}


def _fetch_rest(username):
    url = "%s/users/%s/repos?per_page=100&sort=pushed&type=owner" % (_API, username)
    raw = _rest_json(url)
    if not isinstance(raw, list):
        raise _NetError("REST 仓列表结构异常")
    repos = [_norm_rest(r) for r in raw]
    pr_total = _open_pr_total_rest(username)
    return repos, pr_total


def _open_pr_total_rest(username):
    """开放 PR 总数(best-effort);search 匿名限流更严,失败/限流 → -1(不升级为整模块失败)。"""
    try:
        url = "%s/search/issues?q=is:pr+is:open+author:%s" % (_API, username)
        j = _rest_json(url, timeout=15)
        return int(j.get("total_count", -1))
    except (_NetError, _RateLimit, ValueError, TypeError, AttributeError):
        return -1


# —— 拍平为扁平标量 outputs ——

def flatten(repos, pr_total, username, source, now):
    """过滤后的 repos(已排序)→ 扁平 outputs。repos 为统一结构 dict 列表。"""
    stars_total = sum(int(r.get("stars") or 0) for r in repos)
    shown = repos[:MAX_REPOS]
    pr_txt = ("PR %d" % pr_total) if pr_total is not None and pr_total >= 0 else ""
    summary = "★ %d" % stars_total + ("  ·  %s" % pr_txt if pr_txt else "")
    out = {
        "Title": "GitHub", "User": str(username or ""), "Source": source,
        "Count": len(shown), "StarsTotal": stars_total,
        "StarsTotalText": "★ %d" % stars_total,
        "OpenPrTotal": int(pr_total) if pr_total is not None else -1,
        "OpenPrText": pr_txt, "SummaryText": summary,
    }
    for i in range(MAX_REPOS):
        n = i + 1
        if i < len(shown):
            r = shown[i]
            stars = int(r.get("stars") or 0)
            lang = r.get("language") or ""
            act = activity_label(r.get("pushed_at"), now)
            meta = "★ %d" % stars + ("  ·  %s" % act if act else "")
            out["Repo%dName" % n] = str(r.get("name") or "")
            out["Repo%dStars" % n] = stars
            out["Repo%dStarsText" % n] = "★ %d" % stars
            out["Repo%dLang" % n] = str(lang)
            out["Repo%dActivity" % n] = act
            out["Repo%dDotColor" % n] = lang_color(lang)
            out["Repo%dUrl" % n] = str(r.get("url") or "")
            out["Repo%dMetaText" % n] = meta
        else:                                          # 空槽位:透明点 + 空文本
            out["Repo%dName" % n] = ""
            out["Repo%dStars" % n] = 0
            out["Repo%dStarsText" % n] = ""
            out["Repo%dLang" % n] = ""
            out["Repo%dActivity" % n] = ""
            out["Repo%dDotColor" % n] = "0,0,0,0"
            out["Repo%dUrl" % n] = ""
            out["Repo%dMetaText" % n] = ""
    return out


def collect(cfg):
    """采集某用户公开仓 → 扁平 outputs 或结构化 err。"""
    username = str(cfg.get("username") or "").strip()
    if not username:
        return _err("bug", False,
                    "config.username 为空:请在 config.json 填 GitHub 用户名(示例 octocat)。")
    include_forks = bool(cfg.get("include_forks"))
    use_gh = bool(cfg.get("use_gh_cli", True))
    now = datetime.now(timezone.utc)

    source = None
    repos = pr_total = None
    if use_gh and _gh_available():
        try:
            repos, pr_total = _fetch_gh(username, MAX_REPOS)
            source = "gh"
        except _NetError:
            repos = None                                # gh 失败 → 降级 REST
    if repos is None:
        try:
            repos, pr_total = _fetch_rest(username)
            source = "rest"
        except _RateLimit:
            return _err("rate_limit", True,
                        "GitHub REST 匿名限流(60 次/小时);装并登录 gh CLI(gh auth login)可大幅提额,或稍后重试。")
        except _NetError:
            return _err("network", True,
                        "GitHub 数据获取失败(网络/超时/用户不存在);检查联网、用户名,或装 gh CLI 后重试。")

    filtered = filter_repos(repos, username, include_forks)
    return flatten(filtered, pr_total, username, source, now)


def main(argv=None):
    ap = argparse.ArgumentParser(description="GitHub 仓库动态采集器(gh CLI 优先 / REST 匿名降级)")
    ap.add_argument("--config", default=None, help="config.json 路径")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    try:
        res = collect(cfg)
    except Exception as e:
        res = _err("bug", False, "GitHub 采集器未预期异常:%s" % type(e).__name__)
    _emit(res)
    return 0 if "ok" not in res else 1


if __name__ == "__main__":
    sys.exit(main())
