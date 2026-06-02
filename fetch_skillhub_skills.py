#!/usr/bin/env python3
"""
抓取 SkillHub 全量技能并按分类生成索引。

输出文件：
1) skillhub_skills_all.json
2) skillhub_category_index.json
3) skillhub_category_index.md
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_URL = "https://api.skillhub.cn/api/skills"
DEFAULT_PAGE_SIZE = 100
DEFAULT_SORT_BY = "score"
DEFAULT_ORDER = "desc"

HEADERS = {
    "accept": "*/*",
    "accept-language": "zh-CN,zh;q=0.9",
    "origin": "https://skillhub.cn",
    "referer": "https://skillhub.cn/",
    "sec-ch-ua": '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
    ),
}


def curl_get_json(url: str, timeout: int = 30) -> dict[str, Any]:
    """使用 curl 获取 JSON（适配某些本机网络环境）。"""
    cmd = [
        "curl",
        "-sS",
        "--max-time",
        str(timeout),
        url,
    ]
    for k, v in HEADERS.items():
        cmd.extend(["-H", f"{k}: {v}"])

    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout + 5,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"curl 超时: {url}") from exc
    if proc.returncode != 0:
        raise RuntimeError(f"curl 请求失败(code={proc.returncode}): {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def http_get_json(url: str, timeout: int = 30, retries: int = 3) -> dict[str, Any]:
    """请求 JSON 接口并返回 dict，包含简单重试。"""
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            request = Request(url=url, headers=HEADERS, method="GET")
            with urlopen(request, timeout=timeout) as response:
                payload = response.read().decode("utf-8")
                return json.loads(payload)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            # urllib 在部分环境可能失败，尝试 curl 回退
            try:
                return curl_get_json(url, timeout=timeout)
            except Exception as curl_exc:  # noqa: BLE001
                last_error = curl_exc
                if attempt < retries:
                    time.sleep(0.7 * attempt)
                else:
                    break

    assert last_error is not None
    raise RuntimeError(f"请求失败: {url}\n错误: {last_error}") from last_error


def normalize_category(raw: Any) -> str:
    if isinstance(raw, str):
        clean = raw.strip()
        return clean if clean else "uncategorized"
    return "uncategorized"


def build_page_url(page: int, page_size: int, sort_by: str, order: str) -> str:
    query = urlencode(
        {
            "page": page,
            "pageSize": page_size,
            "sortBy": sort_by,
            "order": order,
        }
    )
    return f"{API_URL}?{query}"


def extract_skills_from_response(resp: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    if resp.get("code") != 0:
        raise RuntimeError(f"接口返回异常 code={resp.get('code')}, message={resp.get('message')}")

    data = resp.get("data") or {}
    skills = data.get("skills") or []
    if not isinstance(skills, list):
        raise RuntimeError("接口字段 data.skills 非列表")

    total = data.get("total")
    if not isinstance(total, int):
        total = len(skills)

    return skills, total


def fetch_all_skills(page_size: int, sort_by: str, order: str, max_pages: int | None = None) -> list[dict[str, Any]]:
    first_url = build_page_url(page=1, page_size=page_size, sort_by=sort_by, order=order)
    first_resp = http_get_json(first_url)
    first_skills, total = extract_skills_from_response(first_resp)

    all_skills = list(first_skills)
    total_pages = max(1, math.ceil(total / page_size))
    if max_pages is not None:
        total_pages = min(total_pages, max_pages)
    print(f"[INFO] total={total}, page_size={page_size}, total_pages={total_pages}", flush=True)

    for page in range(2, total_pages + 1):
        page_url = build_page_url(page=page, page_size=page_size, sort_by=sort_by, order=order)
        resp = http_get_json(page_url)
        page_skills, _ = extract_skills_from_response(resp)
        all_skills.extend(page_skills)
        if page % 5 == 0 or page == total_pages:
            print(f"[INFO] fetched page {page}/{total_pages}, current={len(all_skills)}", flush=True)

    # 去重（优先 slug，其次 name+ownerName）
    deduped: dict[str, dict[str, Any]] = {}
    for skill in all_skills:
        slug = str(skill.get("slug") or "").strip()
        if slug:
            key = f"slug:{slug}"
        else:
            name = str(skill.get("name") or "").strip()
            owner = str(skill.get("ownerName") or "").strip()
            key = f"name_owner:{name}::{owner}"
        deduped[key] = skill

    result = list(deduped.values())
    print(f"[INFO] raw={len(all_skills)}, deduped={len(result)}", flush=True)
    return result


def build_category_index(skills: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for skill in skills:
        category = normalize_category(skill.get("category"))
        grouped[category].append(skill)

    # 类别内按 score desc，再按 installs desc
    for cat in grouped:
        grouped[cat].sort(
            key=lambda s: (
                float(s.get("score") or 0),
                int(s.get("installs") or 0),
            ),
            reverse=True,
        )

    category_items: dict[str, Any] = {}
    for cat, items in sorted(grouped.items(), key=lambda x: len(x[1]), reverse=True):
        category_items[cat] = {
            "count": len(items),
            "skills": [
                {
                    "name": s.get("name"),
                    "slug": s.get("slug"),
                    "ownerName": s.get("ownerName"),
                    "source": s.get("source"),
                    "installs": s.get("installs"),
                    "downloads": s.get("downloads"),
                    "stars": s.get("stars"),
                    "score": s.get("score"),
                    "homepage": s.get("homepage"),
                    "version": s.get("version"),
                    "tags": s.get("tags"),
                    "category": normalize_category(s.get("category")),
                }
                for s in items
            ],
        }

    return {
        "summary": {
            "total_skills": len(skills),
            "total_categories": len(category_items),
        },
        "categories": category_items,
    }


def render_markdown_index(index_data: dict[str, Any]) -> str:
    lines: list[str] = []
    summary = index_data.get("summary", {})
    categories = index_data.get("categories", {})

    lines.append("# SkillHub 技能分类索引")
    lines.append("")
    lines.append(f"- 技能总数: **{summary.get('total_skills', 0)}**")
    lines.append(f"- 分类总数: **{summary.get('total_categories', 0)}**")
    lines.append("")
    lines.append("## 分类目录")
    lines.append("")

    for cat, data in categories.items():
        lines.append(f"- `{cat}` ({data.get('count', 0)})")

    lines.append("")
    lines.append("## 分类明细")
    lines.append("")

    for cat, data in categories.items():
        lines.append(f"### `{cat}` ({data.get('count', 0)})")
        lines.append("")
        for i, skill in enumerate(data.get("skills", []), start=1):
            name = skill.get("name") or "-"
            slug = skill.get("slug") or "-"
            owner = skill.get("ownerName") or "-"
            score = skill.get("score") or 0
            installs = skill.get("installs") or 0
            source = skill.get("source") or "-"
            homepage = skill.get("homepage") or ""
            if homepage:
                lines.append(
                    f"{i}. **{name}** (`{slug}`) - owner: `{owner}`, score: `{score}`, "
                    f"installs: `{installs}`, source: `{source}`, [链接]({homepage})"
                )
            else:
                lines.append(
                    f"{i}. **{name}** (`{slug}`) - owner: `{owner}`, score: `{score}`, "
                    f"installs: `{installs}`, source: `{source}`"
                )
        lines.append("")

    return "\n".join(lines)


def write_json(path: Path, content: Any) -> None:
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="抓取 SkillHub 全量技能并生成分类索引")
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE, help="分页大小（默认100，接口上限100）")
    parser.add_argument("--sort-by", type=str, default=DEFAULT_SORT_BY, help="排序字段（默认score）")
    parser.add_argument("--order", type=str, default=DEFAULT_ORDER, choices=["asc", "desc"], help="排序方向")
    parser.add_argument(
        "--output-dir",
        type=str,
        default=".",
        help="输出目录（默认当前目录）",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="最多抓取页数（默认不限制）",
    )
    args = parser.parse_args()

    if args.page_size <= 0 or args.page_size > 100:
        print("[ERROR] page-size 必须在 1~100 之间", file=sys.stderr)
        return 2

    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        skills = fetch_all_skills(
            page_size=args.page_size,
            sort_by=args.sort_by,
            order=args.order,
            max_pages=args.max_pages,
        )
        index_data = build_category_index(skills)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    all_file = out_dir / "skillhub_skills_all.json"
    index_json_file = out_dir / "skillhub_category_index.json"
    index_md_file = out_dir / "skillhub_category_index.md"

    write_json(all_file, {"total": len(skills), "skills": skills})
    write_json(index_json_file, index_data)
    index_md_file.write_text(render_markdown_index(index_data), encoding="utf-8")

    print(f"[OK] 已输出: {all_file}")
    print(f"[OK] 已输出: {index_json_file}")
    print(f"[OK] 已输出: {index_md_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
