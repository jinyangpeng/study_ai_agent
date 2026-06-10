---
name: 新建功能
about: 提交新功能 / Skill / Provider / Tool
---

## 概要

<!-- 一句话说明这个 PR 做了什么 -->

## 关联 Issue

<!-- "Closes #123" / "Refs #456" -->

## 改动类型

- [ ] 新 Skill
- [ ] 新 Provider
- [ ] 新 Tool / Middleware
- [ ] Bug 修复
- [ ] 重构
- [ ] 文档
- [ ] 测试
- [ ] 其他

## 改动文件

<!-- 关键文件清单 -->

## 测试

<!-- 怎么验证、加了哪些测试 -->

## 破坏性变更

- [ ] 是（如是，请在描述顶部加 ⚠️ BREAKING）
- [ ] 否

## 自检清单

- [ ] `make lint && make fmt` 通过
- [ ] `pytest` 通过（或说明了跳过的原因）
- [ ] 前端 `npm run lint && npm run build` 通过
- [ ] 公共组件 / Skill / Provider / Tool 加了 docstring + 类型注解
- [ ] 没有引入新的顶层依赖（或已在 Issue 中讨论）
- [ ] 没有把敏感信息（API Key / .env）写进提交
