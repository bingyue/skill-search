#!/usr/bin/env python3
"""
构建 SkillHub 索引库的“场景视图 + 动作视图”，并补充中文字段。

输入：
  - skillhub_skills_all.json

输出：
  - doc/views/README.md
  - doc/views/scenes/*.md
  - doc/views/actions/*.md
  - doc/catalog/skills_enriched.json
  - doc/catalog/scene_index.json
  - doc/catalog/action_index.json
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


SCENE_RULES: dict[str, tuple[str, ...]] = {
    "电商": (
        "电商",
        "ecom",
        "shopify",
        "amazon",
        "temu",
        "shopee",
        "aliexpress",
        "listing",
        "pdp",
        "sku",
        "商品",
        "选品",
        "店铺",
        "merchant",
    ),
    "出海": (
        "出海",
        "跨境",
        "cross-border",
        "global",
        "海外",
        "international",
        "localization",
        "seo",
        "foreign trade",
        "export",
    ),
    "自媒体": (
        "自媒体",
        "content creator",
        "content creation",
        "new media",
        "社媒",
        "weibo",
        "twitter",
        "x.com",
        "youtube",
        "instagram",
        "facebook",
        "newsletter",
    ),
    "小红书": ("小红书", "xhs", "xiaohongshu", "rednote"),
    "公众号": ("公众号", "微信", "weixin", "wechat", "wecom", "视频号", "企微", "wxwork"),
    "短视频": ("短视频", "视频", "video", "douyin", "tiktok", "剪辑", "subtitle", "字幕", "直播", "transcribe"),
}

ACTION_RULES: dict[str, tuple[str, ...]] = {
    "选题": ("选题", "topic", "trend", "热点", "keyword", "niche", "idea"),
    "写作": ("写作", "文案", "copy", "article", "blog", "rewrite", "润色", "humanizer", "translate", "内容创作"),
    "配图": ("配图", "图片", "图像", "image", "illustration", "logo", "poster", "banner", "封面"),
    "发布": ("发布", "publish", "posting", "post", "scheduler", "distribution", "分发", "推送"),
    "数据分析": ("数据", "分析", "dashboard", "report", "csv", "excel", "bi", "sql", "指标", "funnel", "monitor"),
    "自动化": ("自动化", "automation", "workflow", "agent", "proactive", "pipeline", "orchestrator", "cron"),
}

# 常见英文词到中文的轻量映射（用于英文技能名补中文）
TOKEN_ZH_MAP: dict[str, str] = {
    "ai": "AI",
    "agent": "智能体",
    "agents": "智能体",
    "auto": "自动",
    "automation": "自动化",
    "workflow": "工作流",
    "stock": "股票",
    "market": "市场",
    "analysis": "分析",
    "analytics": "分析",
    "analyzer": "分析器",
    "report": "报告",
    "dashboard": "看板",
    "data": "数据",
    "video": "视频",
    "subtitle": "字幕",
    "audio": "音频",
    "podcast": "播客",
    "image": "图像",
    "design": "设计",
    "logo": "Logo",
    "poster": "海报",
    "content": "内容",
    "writer": "写作",
    "writing": "写作",
    "copy": "文案",
    "publish": "发布",
    "publisher": "发布",
    "wechat": "微信",
    "xhs": "小红书",
    "douyin": "抖音",
    "shopify": "Shopify",
    "amazon": "亚马逊",
    "ecommerce": "电商",
    "ecom": "电商",
    "search": "搜索",
    "research": "研究",
    "monitor": "监控",
    "tracker": "追踪",
    "tool": "工具",
    "helper": "助手",
    "assistant": "助手",
    "generator": "生成器",
    "builder": "构建器",
    "optimizer": "优化器",
    "security": "安全",
    "compliance": "合规",
}


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.lower()
    if isinstance(value, list):
        return " ".join(str(v).lower() for v in value)
    if isinstance(value, dict):
        return " ".join(f"{k}:{v}" for k, v in value.items()).lower()
    return str(value).lower()


def has_chinese(text: str) -> bool:
    return re.search(r"[\u4e00-\u9fff]", text) is not None


def hit_keyword(corpus: str, keyword: str) -> bool:
    kw = keyword.lower().strip()
    if not kw:
        return False
    if has_chinese(kw):
        return kw in corpus
    if " " in kw or "-" in kw:
        return kw in corpus
    return re.search(rf"\b{re.escape(kw)}\b", corpus) is not None


def build_skill_corpus(skill: dict[str, Any]) -> str:
    return " ".join(
        [
            normalize_text(skill.get("name")),
            normalize_text(skill.get("slug")),
            normalize_text(skill.get("description")),
            normalize_text(skill.get("description_zh")),
            normalize_text(skill.get("tags")),
            normalize_text(skill.get("category")),
            normalize_text(skill.get("ownerName")),
        ]
    )


def classify_multi(corpus: str, rules: dict[str, tuple[str, ...]]) -> list[str]:
    matched: list[str] = []
    for label, keywords in rules.items():
        if any(hit_keyword(corpus, kw) for kw in keywords):
            matched.append(label)
    return matched


def translate_name_to_zh(name: str, slug: str) -> str:
    if has_chinese(name):
        return name

    src = f"{name} {slug}".lower()
    src = re.sub(r"[^a-z0-9\-\s_]+", " ", src)
    tokens = [t for t in re.split(r"[\s\-_]+", src) if t]
    if not tokens:
        return f"英文技能：{name}"

    translated: list[str] = []
    mapped = 0
    for token in tokens:
        if token in TOKEN_ZH_MAP:
            translated.append(TOKEN_ZH_MAP[token])
            mapped += 1
        else:
            translated.append(token)

    # 命中太少时，不做生硬机翻，直接保留原名
    if mapped == 0:
        return f"英文技能：{name}"
    if mapped < max(2, len(tokens) // 2):
        return f"英文技能：{name}"

    zh = " ".join(translated)
    zh = re.sub(r"\s+", " ", zh).strip()
    return zh


def pick_summary_zh(skill: dict[str, Any]) -> str:
    desc_zh = str(skill.get("description_zh") or "").strip()
    if desc_zh:
        return desc_zh
    desc = str(skill.get("description") or "").strip()
    if not desc:
        return "暂无描述"
    short = desc[:120].replace("\n", " ")
    return f"英文描述：{short}"


def sort_skills(skills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        skills,
        key=lambda s: (
            float(s.get("installs") or 0),
            float(s.get("downloads") or 0),
            float(s.get("score") or 0),
            float(s.get("stars") or 0),
        ),
        reverse=True,
    )


def md_escape(value: Any) -> str:
    return str(value if value is not None else "").replace("|", r"\|").replace("\n", " ")


def write_view_md(path: Path, title: str, skills: list[dict[str, Any]], view_type: str) -> None:
    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"- 视图类型：**{view_type}**")
    lines.append(f"- 技能数：**{len(skills)}**")
    lines.append("- 排序：按 `installs`、`downloads`、`score`、`stars` 降序")
    lines.append("")
    lines.append("## 技能清单")
    lines.append("")
    lines.append("| # | name | name_zh | slug | owner | installs | source |")
    lines.append("|---:|---|---|---|---|---:|---|")

    for idx, skill in enumerate(skills, start=1):
        lines.append(
            "| {idx} | {name} | {name_zh} | `{slug}` | `{owner}` | {installs} | `{source}` |".format(
                idx=idx,
                name=md_escape(skill.get("name") or "-"),
                name_zh=md_escape(skill.get("name_zh") or "-"),
                slug=md_escape(skill.get("slug") or "-"),
                owner=md_escape(skill.get("ownerName") or "-"),
                installs=int(skill.get("installs") or 0),
                source=md_escape(skill.get("source") or "-"),
            )
        )

    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="生成场景/动作视图并补中文字段")
    parser.add_argument("--input", default="skillhub_skills_all.json", help="输入 JSON 文件")
    parser.add_argument("--doc-dir", default="doc/views", help="文档输出目录")
    parser.add_argument("--catalog-dir", default="doc/catalog", help="索引 JSON 输出目录")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    doc_dir = Path(args.doc_dir).resolve()
    catalog_dir = Path(args.catalog_dir).resolve()
    scenes_dir = doc_dir / "scenes"
    actions_dir = doc_dir / "actions"

    scenes_dir.mkdir(parents=True, exist_ok=True)
    actions_dir.mkdir(parents=True, exist_ok=True)
    catalog_dir.mkdir(parents=True, exist_ok=True)

    raw = json.loads(input_path.read_text(encoding="utf-8"))
    skills = raw.get("skills") or []
    if not isinstance(skills, list):
        raise ValueError("输入格式错误：skills 不是数组")

    print(f"[INFO] 读取 skills: {len(skills)}", flush=True)

    enriched: list[dict[str, Any]] = []
    scene_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    action_index: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for idx, skill in enumerate(skills, start=1):
        corpus = build_skill_corpus(skill)
        scene_tags = classify_multi(corpus, SCENE_RULES)
        action_tags = classify_multi(corpus, ACTION_RULES)

        name = str(skill.get("name") or "")
        slug = str(skill.get("slug") or "")
        name_zh = translate_name_to_zh(name, slug)

        item = dict(skill)
        item["name_zh"] = name_zh
        item["summary_zh"] = pick_summary_zh(skill)
        item["scene_tags"] = scene_tags
        item["action_tags"] = action_tags
        enriched.append(item)

        for scene in scene_tags:
            scene_index[scene].append(item)
        for action in action_tags:
            action_index[action].append(item)

        if idx % 5000 == 0:
            print(f"[INFO] 处理进度: {idx}/{len(skills)}", flush=True)

    # 视图文档
    scene_readme_lines = ["# 按场景看", "", "## 场景目录", ""]
    for i, scene in enumerate(SCENE_RULES.keys(), start=1):
        items = sort_skills(scene_index.get(scene, []))
        filename = f"{i:02d}-{scene}.md"
        write_view_md(scenes_dir / filename, scene, items, "场景")
        scene_readme_lines.append(f"- [{scene} ({len(items)})](./scenes/{filename})")

    action_readme_lines = ["", "## 按动作看", ""]
    for i, action in enumerate(ACTION_RULES.keys(), start=1):
        items = sort_skills(action_index.get(action, []))
        filename = f"{i:02d}-{action}.md"
        write_view_md(actions_dir / filename, action, items, "动作")
        action_readme_lines.append(f"- [{action} ({len(items)})](./actions/{filename})")

    header = [
        "# Skill 索引视图",
        "",
        "本目录提供两个实战视图：",
        "- 按场景看：电商、出海、自媒体、小红书、公众号、短视频",
        "- 按动作看：选题、写作、配图、发布、数据分析、自动化",
        "",
        f"- 技能总数：**{len(skills)}**",
        "",
    ]
    (doc_dir / "README.md").write_text("\n".join(header + scene_readme_lines + action_readme_lines) + "\n", encoding="utf-8")

    # JSON 索引
    catalog_enriched = {
        "total": len(enriched),
        "skills": enriched,
        "notes": {
            "name_zh": "英文技能名自动补中文（规则生成）",
            "scene_tags": list(SCENE_RULES.keys()),
            "action_tags": list(ACTION_RULES.keys()),
        },
    }
    (catalog_dir / "skills_enriched.json").write_text(json.dumps(catalog_enriched, ensure_ascii=False, indent=2), encoding="utf-8")

    scene_json = {k: sort_skills(v) for k, v in scene_index.items()}
    action_json = {k: sort_skills(v) for k, v in action_index.items()}
    (catalog_dir / "scene_index.json").write_text(json.dumps(scene_json, ensure_ascii=False, indent=2), encoding="utf-8")
    (catalog_dir / "action_index.json").write_text(json.dumps(action_json, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] 输出文档目录: {doc_dir}", flush=True)
    print(f"[OK] 输出索引目录: {catalog_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
