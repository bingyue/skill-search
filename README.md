# SkillHub Skills Crawler

一个用于抓取 SkillHub 全量技能列表并自动生成分类索引的 Python 脚本项目。

数据源页面：[`https://skillhub.cn/skills`](https://skillhub.cn/skills)  
API 示例：`https://api.skillhub.cn/api/skills?page=1&pageSize=100&sortBy=score&order=desc`

## 功能特性

- 自动分页抓取 SkillHub 技能数据（根据接口 `total` 计算总页数）
- 支持排序参数（`sortBy` + `order`）
- 自动去重（优先 `slug`，其次 `name + ownerName`）
- 分类归并（空分类统一为 `uncategorized`）
- 输出三份结果：
  - 全量技能清单 JSON
  - 分类索引 JSON
  - 分类索引 Markdown
- 内置网络重试与 `curl` 回退机制（提升兼容性）

## 项目结构

```text
skill-search/
├── fetch_skillhub_skills.py       # 主脚本：抓取 + 分类 + 输出
├── skillhub_skills_all.json       # 全量技能原始清单（运行后生成）
├── skillhub_category_index.json   # 分类索引（运行后生成）
└── skillhub_category_index.md     # 人类可读分类索引（运行后生成）
```

## 环境要求

- Python `3.9+`（推荐 `3.11+`）
- 系统可用 `curl` 命令（用于网络回退）
- 网络可访问 `api.skillhub.cn`

## 快速开始

在项目目录执行：

```bash
python3 fetch_skillhub_skills.py
```

成功后会输出类似日志：

```text
[INFO] total=..., page_size=100, total_pages=...
[INFO] fetched page .../... , current=...
[INFO] raw=..., deduped=...
[OK] 已输出: .../skillhub_skills_all.json
[OK] 已输出: .../skillhub_category_index.json
[OK] 已输出: .../skillhub_category_index.md
```

## 命令参数

```bash
python3 fetch_skillhub_skills.py \
  --page-size 100 \
  --sort-by score \
  --order desc \
  --output-dir . \
  --max-pages 10
```

参数说明：

- `--page-size`：每页条数，范围 `1~100`，默认 `100`
- `--sort-by`：排序字段，默认 `score`
- `--order`：排序方向，`asc` 或 `desc`，默认 `desc`
- `--output-dir`：输出目录，默认当前目录
- `--max-pages`：最多抓取页数（调试时非常有用），默认不限制

## 输出文件说明

### 1) `skillhub_skills_all.json`

全量去重后的技能列表，结构为：

- `total`：技能总数
- `skills`：技能对象数组（保留接口原始字段）

### 2) `skillhub_category_index.json`

分类索引结构，包含：

- `summary.total_skills`
- `summary.total_categories`
- `categories.<category>.count`
- `categories.<category>.skills[]`（按 `score`、`installs` 降序）

### 3) `skillhub_category_index.md`

面向人工阅读，包含：

- 分类目录（分类名 + 数量）
- 每个分类下的技能明细（名称、slug、owner、score、installs、source、链接）

## 常见用法

仅做小样本测试（减少等待时间）：

```bash
python3 fetch_skillhub_skills.py --max-pages 5
```

输出到单独目录：

```bash
python3 fetch_skillhub_skills.py --output-dir ./output
```

## 常见问题

### 1. 为什么全量抓取比较慢？

SkillHub 总量较大（可能数万条），即便 `page-size=100` 也需要抓取很多页。建议先用 `--max-pages` 做联调。

### 2. 为什么会有大量 `uncategorized`？

接口中部分技能 `category` 为空字符串或缺失，脚本会统一归类为 `uncategorized`。

### 3. `urllib` 失败但 `curl` 能通怎么办？

脚本已内置 `curl` 回退逻辑，通常可自动恢复；如仍失败，优先检查本机网络代理、防火墙或 DNS 配置。

## 后续可扩展方向

- 增加增量更新模式（基于 `updated_at`）
- 增加按来源（`source`）和作者（`ownerName`）的二级索引
- 增加 CSV 导出和简单可视化统计
- 增加并发抓取（需控制速率，避免触发风控）

