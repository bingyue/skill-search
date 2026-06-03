#!/usr/bin/env python3
"""
根据 SkillHub 全量数据生成“实用业务分类”文档。

输入：
  - skillhub_skills_all.json

输出：
  - doc/README.md
  - doc/<分类编号>-<slug>.md
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PracticalCategory:
    name: str
    slug: str
    keywords: tuple[str, ...]


CATEGORIES: list[PracticalCategory] = [
    PracticalCategory("小红书运营", "xiaohongshu", ("小红书", "xhs", "xiaohongshu", "rednote")),
    PracticalCategory("公众号与微信生态", "wechat-ecosystem", ("公众号", "微信", "weixin", "wechat", "wecom", "视频号", "企微", "wxwork")),
    PracticalCategory("抖音/短视频与直播", "douyin-video-live", ("抖音", "douyin", "tiktok", "直播", "短视频", "带货直播")),
    PracticalCategory(
        "电商与选品",
        "ecommerce",
        ("电商", "选品", "商品", "listing优化", "pdp", "amazon", "shopify", "temu", "shopee", "aliexpress", "ecom", "店铺", "跨境电商", "review monitor", "产品页", "详情页", "sku", "卖家"),
    ),
    PracticalCategory("出海与跨境增长", "global-growth", ("出海", "跨境", "海外", "localization", "seo", "outreach", "influencer", "foreign trade", "export", "cross-border")),
    PracticalCategory("社媒运营与内容分发", "social-media-ops", ("社媒", "social media", "微博", "weibo", "twitter", "x.com", "facebook", "instagram", "youtube", "分发")),
    PracticalCategory("内容写作与文案", "writing-copy", ("写作", "文案", "copywriting", "blog", "article", "newsletter", "改写", "润色", "humanizer", "内容创作")),
    PracticalCategory("图像设计与品牌视觉", "image-design", ("图像", "图片", "logo", "海报", "封面图", "image", "illustration", "poster", "banner", "comfyui", "midjourney")),
    PracticalCategory("视频制作与剪辑", "video-production", ("视频", "剪辑", "字幕", "分镜", "video", "ffmpeg", "premiere", "jianying", "clip")),
    PracticalCategory("音频与播客", "audio-podcast", ("音频", "播客", "podcast", "asr", "tts", "语音", "录音", "transcript")),
    PracticalCategory("数据分析与报表", "data-analytics", ("数据", "报表", "分析", "dashboard", "excel", "csv", "bi", "sql", "可视化", "funnel", "指标")),
    PracticalCategory("金融投资与商业研究", "finance-investment", ("金融", "股票", "基金", "投研", "量化", "交易", "market", "invest", "polymarket", "财经", "证券")),
    PracticalCategory("搜索采集与研究", "search-research", ("搜索", "search", "research", "crawl", "scrape", "fetch", "采集", "监测", "调研", "news")),
    PracticalCategory("办公协同与文档", "office-collab", ("文档", "表格", "ppt", "word", "excel", "飞书", "lark", "notion", "会议", "calendar", "task")),
    PracticalCategory("开发工具与工程效率", "dev-tools", ("github", "git", "docker", "terminal", "cli", "开发", "代码", "sdk", "mcp", "agent browser", "cursor")),
    PracticalCategory("AI智能体与自动化", "ai-agent-automation", ("agent", "ai", "自动化", "automation", "workflow automation", "proactive", "memory", "self-improving", "ontology")),
    PracticalCategory("安全合规与风控", "security-compliance", ("安全", "合规", "风控", "security", "compliance", "audit", "sanitize", "defender", "vetter", "owasp")),
]

FALLBACK_CATEGORY = "其他通用工具"

ORIGINAL_CATEGORY_FALLBACK: dict[str, str] = {
    "developer-tools": "开发工具与工程效率",
    "content-creation": "内容写作与文案",
    "data-analysis": "数据分析与报表",
    "ai-intelligence": "AI智能体与自动化",
    "productivity": "办公协同与文档",
    "security-compliance": "安全合规与风控",
    "communication-collaboration": "办公协同与文档",
}


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.lower()
    if isinstance(value, list):
        return " ".join(str(v).lower() for v in value)
    return str(value).lower()


def keyword_hit(text: str, keyword: str) -> bool:
    kw = keyword.lower().strip()
    if not kw:
        return False
    if re.search(r"[\u4e00-\u9fff]", kw):
        return kw in text
    if " " in kw or "-" in kw:
        return kw in text
    return re.search(rf"\b{re.escape(kw)}\b", text) is not None


def classify_skill(skill: dict[str, Any]) -> str:
    primary = " ".join([normalize_text(skill.get("name")), normalize_text(skill.get("slug")), normalize_text(skill.get("tags"))])
    secondary = " ".join([normalize_text(skill.get("description")), normalize_text(skill.get("description_zh"))])

    best_name = ""
    best_score = 0
    for cat in CATEGORIES:
        p_hits = sum(1 for kw in cat.keywords if keyword_hit(primary, kw))
        s_hits = sum(1 for kw in cat.keywords if keyword_hit(secondary, kw))
        score = p_hits * 3 + s_hits
        if score > best_score:
            best_score = score
            best_name = cat.name

    if best_score > 0:
        return best_name

    original = normalize_text(skill.get("category")).strip()
    if original in ORIGINAL_CATEGORY_FALLBACK:
        return ORIGINAL_CATEGORY_FALLBACK[original]
    return FALLBACK_CATEGORY


def sort_skills(skills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(skills, key=lambda s: (float(s.get("installs") or 0), float(s.get("downloads") or 0), float(s.get("score") or 0), float(s.get("stars") or 0)), reverse=True)


def safe_filename(title: str) -> str:
    text = title.lower().strip().replace("&", "and")
    text = re.sub(r"[/\\\s]+", "-", text)
    text = re.sub(r"[^0-9a-zA-Z\-\u4e00-\u9fff]+", "", text)
    return text.strip("-") or "category"


def md_escape(value: Any) -> str:
    return str(value if value is not None else "").replace("|", r"\|").replace("\n", " ")


def render_category_md(category: str, skills: list[dict[str, Any]]) -> str:
    lines = [
        f"# {category}",
        "",
        f"- 技能数：**{len(skills)}**",
        "- 排序：按 `installs`、`downloads`、`score`、`stars` 降序",
        "- 说明：本分类为“业务实用优先”的二次归类（参考 yue-skills 场景）",
        "",
        "## 技能清单",
        "",
        "| # | name | slug | owner | installs | source | 原始分类 |",
        "|---:|---|---|---|---:|---|---|",
    ]
    for i, skill in enumerate(skills, start=1):
        lines.append(
            "| {idx} | {name} | `{slug}` | `{owner}` | {installs} | `{source}` | `{raw_cat}` |".format(
                idx=i,
                name=md_escape(skill.get("name") or "-"),
                slug=md_escape(skill.get("slug") or "-"),
                owner=md_escape(skill.get("ownerName") or "-"),
                installs=int(skill.get("installs") or 0),
                source=md_escape(skill.get("source") or "-"),
                raw_cat=md_escape((skill.get("category") or "").strip() or "uncategorized"),
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 SkillHub 实用分类文档")
    parser.add_argument("--input", default="skillhub_skills_all.json", help="输入 JSON 文件路径")
    parser.add_argument("--output-dir", default="doc", help="输出目录")
    args = parser.parse_args()

    input_file = Path(args.input).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    raw = json.loads(input_file.read_text(encoding="utf-8"))
    skills = raw.get("skills") or []
    if not isinstance(skills, list):
        raise ValueError("输入文件格式错误：skills 不是列表")
    print(f"[INFO] 读取到技能: {len(skills)}", flush=True)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for idx, skill in enumerate(skills, start=1):
        grouped[classify_skill(skill)].append(skill)
        if idx % 5000 == 0:
            print(f"[INFO] 已分类: {idx}/{len(skills)}", flush=True)

    for cat_name in list(grouped.keys()):
        grouped[cat_name] = sort_skills(grouped[cat_name])

    ordered_categories = sorted(grouped.items(), key=lambda x: len(x[1]), reverse=True)

    index_lines = [
        "# SkillHub 实用分类索引",
        "",
        "本目录基于 `skillhub_skills_all.json` 二次整理，兼顾：",
        "- SkillHub 原始分类（developer-tools / content-creation 等）",
        "- yue-skills 的业务场景分类思路",
        "- 常见实战场景：电商、自媒体、内容媒体、出海、小红书、公众号等",
        "",
        f"- 技能总数：**{len(skills)}**",
        f"- 分类总数：**{len(ordered_categories)}**",
        "",
        "## 分类目录",
        "",
    ]

    for idx, (category, cat_skills) in enumerate(ordered_categories, start=1):
        filename = f"{idx:02d}-{safe_filename(category)}.md"
        (output_dir / filename).write_text(render_category_md(category, cat_skills), encoding="utf-8")
        print(f"[INFO] 已生成: {filename} ({len(cat_skills)})", flush=True)
        index_lines.append(f"- [{category} ({len(cat_skills)})](./{filename})")

    (output_dir / "README.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    print(f"[OK] 技能总数: {len(skills)}")
    print(f"[OK] 分类总数: {len(ordered_categories)}")
    print(f"[OK] 输出目录: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
