# 知识库治理规程 (Documentation Governance)

本仓库文档治理遵循 Diátaxis 四象限架构与 Docs-as-Code 门禁，完整技能规程见 `.agents/skills/doc-governance/SKILL.md`。

## 目录职责

| 目录 | 职责 | 红线 |
| :--- | :--- | :--- |
| `reference/` | 权威机械规格：API 契约、数据模型、错误信封 | 严禁混入教学或推演；未定案内容禁止写入 |
| `proposals/` | RFC 提案孵化（Draft → Accepted），定案后结晶下沉 | 定案后必须解构下沉并归档至 `archive/` |
| `tutorials/` | 学习导向教程 | 必须可跟做，从零到可运行 |
| `how-to/` | 任务导向操作配方 | 面向已掌握基础的用户解决具体任务 |
| `explanation/` | 架构剖析、ADR（MADR 3.0，Append-Only）、调研 | 回答 Why，不回答 How |
| `project/` | changelog / backlog / roadmap / plans | 工程演进记录闭环；plans 为 goal-loop 执行计划归档 |

## 联动规则（Sync Mode）

代码变更必须逆向联动文档：

- 调用新的 SDK 接口或封装新函数 → 同步 `reference/api/baidu-pan-sdk.md` 第 3 节代码映射
- 授权方式 / token 生命周期变更 → 同步 `reference/api/baidu-pan-sdk.md` 3.1 与 changelog
- 目录结构或依赖管理变更 → 同步根 `README.md` 与 `docs/index.md`
- 功能交付 → 追加 `project/changelog.md` 记录，关闭 `project/backlog.md` 对应项

## 门禁（提交前必须通过）

```bash
python3 scripts/check-doc-links.py --root docs   # 零断链
python3 scripts/trim-revision.py --root docs --fix --keep 5
python3 scripts/generate-llms-txt.py --root docs --output docs/llms.txt
```

## 写作规范

- 语言：中文正文，标识符/路径保持英文原样；文件名全小写 kebab-case。
- 引用：文档间相对链接必须显式 `.md` 后缀；禁止裸路由与绝对物理路径。
- 修订历史：每份文档保留最近 5 条，格式见脚手架模板。
- 单文档不超过 800 行，超出即拆分为总纲-子册。
