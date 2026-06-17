"""LLM 调用和 tool 调用的日志回调 handler。"""

from datetime import datetime
from pathlib import Path

from langchain_core.callbacks import BaseCallbackHandler


class LoggingHandler(BaseCallbackHandler):
    """把 LLM 和 tool 调用同时打到控制台和文件。"""

    name = "logger"

    def _now_ms(self) -> str:
        now = datetime.now()
        return now.strftime("%Y-%m-%d %H:%M:%S") + f".{now.microsecond // 1000:03d}"

    def _log(self, msg: str) -> None:
        print(msg, flush=True)
        try:
            log_dir = Path(__file__).resolve().parent / "logs"
            log_dir.mkdir(exist_ok=True)
            log_file = log_dir / f"agent_{datetime.now().strftime('%Y-%m-%d')}.log"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            pass

    def on_chat_model_start(self, serialized, messages, **kwargs):
        ts = self._now_ms()
        try:
            prompts = [str(m)[:500] for m in (messages[0] if messages else [])]
        except Exception:
            prompts = [str(messages)[:500]]
        self._log(f"{ts}  [name={self.name} type=model-start] prompts={prompts}")

    def on_chat_model_end(self, response, **kwargs):
        ts = self._now_ms()
        try:
            output = str(response)[:500]
        except Exception:
            output = "..."
        self._log(f"{ts}  [name={self.name} type=model-end] output={output}")

    def on_tool_start(self, serialized, input_str, **kwargs):
        ts = self._now_ms()
        name = serialized.get("name", "unknown") if isinstance(serialized, dict) else "unknown"
        self._log(f"{ts}  [name={self.name} type=tool-start] tool={name}, input={input_str}")

    def on_tool_end(self, output, **kwargs):
        ts = self._now_ms()
        self._log(f"{ts}  [name={self.name} type=tool-end] output={output}")
