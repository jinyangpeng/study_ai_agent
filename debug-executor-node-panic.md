# Debug: executor_node panic in langgraph run

**Session ID**: `executor-node-panic`
**Status**: `[OPEN]`
**Created**: 2026-06-11

## 症状

调用 `POST /`（AG-UI run 端点）时，后端 SSE 流中断，server 抛出：

```
AG-UI run 异常，中断事件流
[Traceback omitted — 末端异常行被截断，未贴出]
```

错误最后落点在：

```
File ".../src/core/nodes.py", line 137, in executor_node
    result = await agent.ainvoke(
        {"messages": state["messages"] + [plan_msg]}
    )
```

上游是 langgraph `_panic_or_proceed` → `raise exc`：
```
File ".../langgraph/pregel/_runner.py", line 687, in _panic_or_proceed
    raise exc
```

## 用户信息

- 后端 Python 错误
- 错误正文 / 堆栈等待用户补全（最关键的是栈底 `XXXError: <message>` 行）
- 用户当前在 IDE 中打开了 `src/providers/qwen.py`（行 32：`qwen-plus-2025-07-14`），**模型名可能是线索之一**

## 复现路径（推测）

1. `frontend -> POST /`
2. `server.py` 路由匹配 `forwarded_props.skill`
3. `LangGraphAgent.run()` -> LangGraph pregel 执行 `qa` 图（或其它 skill）
4. planner 节点正常返回 → 进入 `executor_node`
5. `executor_node` 内 `agent.ainvoke(...)` 抛异常
6. langgraph 把 task 标 failed → `_panic_or_proceed` 抛出
7. 上层 SSE 流的 `try/except` 捕获并下发 `RUN_ERROR` 事件

## 假设（待运行时证据证伪 / 证实）

1. **H1（最可能）—— 真实异常被截断**：栈底 `Exception: <message>` 行被用户漏贴。最有可能的 `XXXError` 是 qwen API 返回的某个错误码（400 / 401 / 404 / 429 / 5xx）。需要先拿到 message 才能定。
2. **H2 —— HITL middleware 在非交互上下文里死锁**：`make_executor_node` 启用了 `HumanInTheLoopMiddleware`（见 `nodes.py:117-123`）。SSE 一次性跑到底，没有"用户回传 approve/reject"的回路，HITL 中断点会**挂起或抛错**。
3. **H3 —— plan_msg 的 `model_dump()` 在 plan 是 dict 而非 Pydantic 时崩溃**：planner 输出走 `state["plan"]`，若 aggregator 或 reviewer 把它写成了 dict，再被 executor 取出来 `.model_dump()` 会 AttributeError。但 traceback 看上去是 executor 内部 agent 抛错，不是 plan_msg 构造，所以此假设相对弱。
4. **H4 —— `state["messages"]` 在传入前已有损坏**：可能上游 reviewer 节点把 `state["messages"]` 写成了不可序列化的对象，或包含 tool_calls 残缺。LangGraph 的 message 校验在 ainvoke 阶段会报错。
5. **H5 —— qwen API 报 model not found / 参数不兼容**：用户当前在 `qwen.py:32` 上 —— 模型名 `qwen-plus-2025-07-14` 是带日期的版本。DashScope OpenAI 兼容端点有可能对该特定日期 snapshot 不识别 → 401/400。

## 下一步

请用户补全：
1. **栈底真正的异常类型 + message**（`raise exc` 之后那行）
2. （如果方便）出错时前端请求的 body：`threadId` / `forwarded_props` / `messages` 的最后一条 user 内容

收到后再决定插桩位置（H1 之外是否还需要额外 instrument）。

## 协议约束

- 在拿到 message 之前，不动业务代码
- 第一处代码改动只能是插桩（"region debug-point"）
- 用户确认 fixed/abort 后再清理
