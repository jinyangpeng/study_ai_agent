# Tests 目录说明

按主题分类的测试文件。

## 目录结构

```
tests/
├── conftest.py              # pytest 公共配置
├── unit/                    # 单元测试（无需外部依赖）
│   ├── test_tools.py        # tools 测试
│   ├── test_attr.py         # tool 属性测试
│   └── test_autoload.py     # 自动加载测试
├── llm/                     # LLM 模型测试（需 API Key）
│   ├── test_chat.py         # 通用聊天
│   ├── test_zhipu.py        # 智谱（早期）
│   ├── test_zhipuai.py      # 智谱（新版）
│   ├── test_deepseek.py     # DeepSeek
│   └── test_qianfan.py      # 千帆
└── integration/             # 集成测试（需运行后端服务）
    ├── test_server.py       # 服务器
    ├── test_proxy.py        # 代理
    └── test_full.py         # 端到端
```

## 运行测试

```bash
# 全部
pytest tests/

# 仅单元测试
pytest tests/unit/

# 仅 LLM 测试（需要 API Key）
pytest tests/llm/

# 仅集成测试（需要先启动后端）
uvicorn agent.server:app &
pytest tests/integration/
```

## 编写新测试

1. 选择合适分类目录
2. 命名为 `test_*.py`
3. 使用 pytest 风格（`def test_xxx():`）
4. 测试间共享的 fixture 放在 `conftest.py`
