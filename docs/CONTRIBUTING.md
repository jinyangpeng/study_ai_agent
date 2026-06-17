# 贡献指南（CONTRIBUTING）

欢迎贡献！提交 PR 之前请先读这份文档。

## 行为准则

请保持友好、专业的沟通。所有 Issue / PR / Discussion 适用本仓库 [MIT 许可证](../LICENSE)。

## 我能贡献什么

- **修 Bug**：在 Issue 里搜关键词或自己提一个
- **新 Skill / Provider / Tool**：参考 [AGENTS.md](AGENTS.md) 的标准流程
- **文档 / 示例**：欢迎补充 README、教程、Jupyter Notebook
- **测试**：单元 / 集成 / 一次性诊断脚本都欢迎
- **性能 / 重构**：建议先开 Issue 讨论再动手

## 提 Issue

提交 Bug 报告前请：

1. 在 Issue 列表里搜一下，避免重复
2. 用对应的模板（`.github/ISSUE_TEMPLATE/bug_report.md` / `feature_request.md`）
3. 附上：
   - 操作系统 / Python / Node 版本
   - 复现步骤（最小可运行片段）
   - 期望 / 实际行为
   - 后端日志（`LOG_LEVEL=DEBUG` 启动）

## 提 PR

### 1. Fork + 分支

```bash
git clone https://github.com/<you>/study_ai_agent.git
cd study_ai_agent
git checkout -b feat/your-feature
```

分支命名建议：

- `feat/<short-name>`：新功能
- `fix/<short-name>`：修 bug
- `docs/<short-name>`：纯文档
- `refactor/<short-name>`：重构
- `chore/<short-name>`：杂项

### 2. 改代码

请遵守：

- 后端遵循 `pyproject.toml` 的 ruff 配置（`just lint` / `just fmt`）
- 前端遵循 `eslint.config.js`（`npm run lint`）
- 公共模块 / Skill / Provider / Tool 加 **类型注解 + docstring**（中英文都可以，和现有风格保持一致）
- 不要在生产代码里 `print`；走 `logging`
- 不要新增顶层依赖；如确需，先开 Issue 讨论

### 3. 改测试

- 新增 / 修改的功能 **必须** 配单测
- 跑：`just lint && pytest`
- 前端：`npm run lint && npm run build`

### 4. 提交信息

参考 [Conventional Commits](https://www.conventionalcommits.org/)：

```text
feat(skills): add data_analysis skill with sql_write HITL

- 新增 DataAnalysisSkill（COMPUTATION + DATABASE + INFO 三类工具）
- sql_write / shell_exec 走 approve/reject 审批门禁
- /skeletons 自动暴露

Refs: #123
```

格式：

```text
<type>(<scope>): <subject>

<body>

<footer>
```

常用 type：`feat` / `fix` / `docs` / `refactor` / `test` / `chore` / `perf`

### 5. 推 + 开 PR

```bash
git push origin feat/your-feature
# 在 GitHub 上点 "Compare & pull request"，按 .github/PULL_REQUEST_TEMPLATE.md 填
```

PR 描述里请说明：

- **动机 / 解决什么问题**
- **改动概览**（对应哪些文件 / 模块）
- **测试**（怎么验证，加了什么测试）
- **截图 / 日志**（如适用）
- **破坏性变更**（如有，在描述顶部加 ⚠️ BREAKING）

## 风格指南

### Python

- PEP 8 + ruff 默认规则（`pyproject.toml` 已配）
- 行宽 120（`line-length = 120`）
- 类型注解贯穿（`mypy` 不强制，但建议）
- 模块顶部按规范放 docstring + 注释说明"为什么这么设计"
- 中文 / 英文注释都可以，但同一份文件内保持一致

### TypeScript

- ESLint + `@typescript-eslint`（`eslint.config.js`）
- React 组件用函数组件 + hooks
- 全局样式走 Tailwind CSS class，复杂组件用 CSS Modules
- 路径别名用 `@/`

### 提交粒度

- 一个 PR 一个主题，不要混搭
- 大量修改前先开 Issue 对齐
- WIP 状态用 `Draft PR`

## 发布 / 版本

本项目尚在学习阶段，没有严格语义化版本。重大变更会写进 [CHANGELOG](../CHANGELOG)（如无则跳过）。

## 安全

发现安全漏洞请 **不要** 公开 Issue，邮件联系维护者（见仓库 `CODEOWNERS` / `About`）。

## 许可

提交代码即默认同意以 [MIT](../LICENSE) 协议开源。
