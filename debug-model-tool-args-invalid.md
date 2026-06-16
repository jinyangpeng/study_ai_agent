# Debug Session: model-tool-args-invalid

> Status: [OPEN]

## 症状
- `POST /` 返回 200，但 AG-UI 事件流中途异常中断
- 服务端 traceback 终点：
  `openai.APIError: <400> InternalError.Algo.InvalidParameter: The "function.arguments" parameter of the code model must be in JSON format.`
- 失败位置：`src/core/strategies/p_e_r_a.py:185` 的 `agent.ainvoke(...)`（execute_node）
- 失败上下文：PERA 策略的 execute 阶段，agent 带 `skill.tools`（含 `make_safe` 包过的 `duckduckgo_results_json`）

## 假设（待证据验证）
1. **H1**：模型在 streaming 过程中 `function.arguments` JSON 非法（多行/转义/截断），上游 Qwen / Qianfan 端点 400。失败工具很可能是 `duckduckgo_results_json`（之前 timeout 时返回的 JSON 错误结果把模型"喂晕"了）。
2. **H2**：`make_safe` 把 `{"ok": false, ...}` 错误 JSON 当作 tool_message 发回，模型把整个 JSON 字符串当 schema 参考，二次 tool call 时直接拿这段字符串当 arguments 输出。
3. **H3**：`safe_tool` 包装后丢掉了原 `BaseTool.args_schema`，导致 OpenAI 协议层把 tool definition 渲染成空 schema 或非法 schema，模型按空 schema 自由发挥出非法 JSON。
4. **H4**：模型本身在 `create_agent(response_format=Plan/Review)` 子图里能 work，但 execute_node 没设 `response_format`，流式 `tool_choice="auto"` 触发了上游"code model" 严格校验。
5. **H5**：网络/上游瞬时问题：第一次 tool call 还在飞，客户端断开重试导致 arguments 截断。需看 `req_id` / 时间戳关联。

## 待插桩点
- `safe_tool._safe_run/_safe_arun` —— 记录 tool 名称、args 摘要、原始返回 / 异常（已有 `logger.warning`，但缺 request_id）
- `p_e_r_a._make_execute_node` 入口 —— 记录 tools 列表、`agent.ainvoke` 入参 `messages` 数量、模型名
- 任何地方加 `req_id` 把"模型请求 → 工具调用 → 工具结果 → 模型回复 → 异常"串起来

## 状态
- [OPEN] 等待插桩 + 重跑
