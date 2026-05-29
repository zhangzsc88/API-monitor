"""
DeepSeek Monitor - Session Token 追踪模块
从 OpenClaw session JSONL 文件中提取 DeepSeek 实际 token 消耗
支持增量扫描（每次只读新增数据）
"""
import json
import os
import time
import logging
from datetime import date, datetime, timezone, timedelta

logger = logging.getLogger("deepseek-monitor")

# CST = UTC+8
CST = timezone(timedelta(hours=8))

# 缓存文件路径
CACHE_FILE = None  # 由外部设置


def _get_cache_path():
    """获取缓存路径"""
    global CACHE_FILE
    if CACHE_FILE:
        return CACHE_FILE
    try:
        from .config import CONFIG_DIR
        CACHE_FILE = str(CONFIG_DIR / "session_cache.json")
        return CACHE_FILE
    except ImportError:
        CACHE_FILE = os.path.join(os.path.expanduser("~"), ".deepseek-monitor", "session_cache.json")
        return CACHE_FILE


def _get_session_dirs():
    """获取所有 Agent 的 session 目录"""
    agents_dir = "/root/.openclaw/agents"
    dirs = []
    if not os.path.isdir(agents_dir):
        return dirs
    for agent in os.listdir(agents_dir):
        session_dir = os.path.join(agents_dir, agent, "sessions")
        if os.path.isdir(session_dir):
            dirs.append(session_dir)
    return dirs


def _get_session_files():
    """获取所有 session 数据文件（包括 .jsonl 和 .jsonl.reset 备份）"""
    files = []
    skip_suffixes = ('.trajectory.jsonl', '.trajectory-path.json')
    skip_names = ('sessions.json',)
    for d in _get_session_dirs():
        for fname in os.listdir(d):
            fpath = os.path.join(d, fname)
            if not os.path.isfile(fpath):
                continue
            if fname in skip_names:
                continue
            if any(fname.endswith(s) for s in skip_suffixes):
                continue
            files.append(fpath)
    return files


def _is_today(ts_str):
    """判断时间戳是否为今天（CST）"""
    try:
        # ISO 格式: "2026-05-29T12:00:41.396Z"
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        dt_cst = dt.astimezone(CST)
        return dt_cst.date() == date.today()
    except Exception:
        return False


def _load_cache():
    """加载增量扫描缓存"""
    path = _get_cache_path()
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return {"date": None, "total_tokens": 0, "files": {}, "last_scan": None}


def _save_cache(cache):
    """保存缓存"""
    path = _get_cache_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cache["last_scan"] = datetime.now(CST).isoformat()
    with open(path, "w") as f:
        json.dump(cache, f, indent=2)


def scan_today_tokens(full_scan=False):
    """
    扫描今日 DeepSeek token 消耗
    返回: {
        "total_tokens": int,
        "input_tokens": int,
        "output_tokens": int,
        "cache_read": int,
        "cache_write": int,
        "scanned_files": int,
        "new_lines": int,
        "scan_time_ms": int,
    }
    """
    start = time.time()
    today = date.today().isoformat()
    cache = _load_cache()

    # 日期变了，重置缓存
    if cache.get("date") != today:
        logger.info(f"日期变更 {cache.get('date')} → {today}，重置缓存")
        cache = {"date": today, "total_tokens": 0, "files": {}, "last_scan": None}

    totals = {
        "total_tokens": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read": 0,
        "cache_write": 0,
    }

    # 如果是全量扫描（首次/手动），清除文件缓存和累计值
    if full_scan:
        cache["files"] = {}
        cache["total_tokens"] = 0

    files = _get_session_files()
    scanned = 0
    new_lines = 0

    for filepath in files:
        try:
            stat = os.stat(filepath)
            current_size = stat.st_size
            current_mtime = stat.st_mtime

            # 从缓存获取上次扫描位置
            file_cache = cache["files"].get(filepath, {})
            last_offset = file_cache.get("offset", 0) if not full_scan else 0
            last_mtime = file_cache.get("mtime", 0)

            # 文件未变化且非全量扫描 → 跳过
            if not full_scan and current_mtime <= last_mtime and current_size >= last_offset:
                continue

            # 如果 mtime 变了但文件更小了（被截断），从头扫
            if current_mtime > last_mtime and current_size < last_offset:
                last_offset = 0

            # 文件已读完 → 跳过
            if current_size <= last_offset and not full_scan:
                continue

            with open(filepath, "r") as f:
                if last_offset > 0:
                    f.seek(last_offset)
                    # 跳到下一行开头（避免从行中间开始）
                    if last_offset > 0:
                        f.readline()

                for line in f:
                    new_lines += 1
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # 只处理 assistant 消息
                    if msg.get("type") != "message":
                        continue
                    inner = msg.get("message", {})
                    if inner.get("role") != "assistant":
                        continue

                    # 只计算 DeepSeek provider
                    provider = inner.get("provider", "")
                    if "deepseek" not in provider.lower():
                        continue

                    # 过滤今天的消息
                    ts = msg.get("timestamp", "")
                    if not _is_today(ts):
                        continue

                    usage = inner.get("usage")
                    if not usage:
                        continue

                    totals["total_tokens"] += usage.get("totalTokens", 0)
                    totals["input_tokens"] += usage.get("input", 0)
                    totals["output_tokens"] += usage.get("output", 0)
                    totals["cache_read"] += usage.get("cacheRead", 0)
                    totals["cache_write"] += usage.get("cacheWrite", 0)

            # 更新文件缓存
            cache["files"][filepath] = {
                "offset": current_size,
                "mtime": current_mtime,
            }
            scanned += 1

        except FileNotFoundError:
            # 文件被删除了，从缓存中移除
            cache["files"].pop(filepath, None)
        except Exception as e:
            logger.warning(f"扫描 {filepath} 失败: {e}")
            continue

    # 更新总计（增量累加，跨天重置已在上面处理）
    cache["total_tokens"] = cache.get("total_tokens", 0) + totals["total_tokens"]
    cache["date"] = today

    # 清理已不存在的文件
    cache["files"] = {
        k: v for k, v in cache["files"].items() if os.path.exists(k)
    }

    _save_cache(cache)

    elapsed = int((time.time() - start) * 1000)
    logger.info(
        f"Token 扫描完成: {totals['total_tokens']:,} tokens "
        f"(扫描 {scanned} 个文件, {new_lines} 新行, {elapsed}ms)"
    )

    return {
        **totals,
        "scanned_files": scanned,
        "new_lines": new_lines,
        "scan_time_ms": elapsed,
    }


def get_cached_total():
    """获取缓存中的今日总额（不重新扫描）"""
    cache = _load_cache()
    today = date.today().isoformat()
    if cache.get("date") == today:
        return cache.get("total_tokens", 0)
    return 0
