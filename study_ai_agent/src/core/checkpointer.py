"""LangGraph checkpointer 工厂（生产级实现）。

设计要点
--------

* **异步连接池**（:class:`psycopg_pool.AsyncConnectionPool`）：
  整个进程共享一个池，避免每请求建立/释放 TCP 连接的开销。
* **异步 saver**（:class:`langgraph.checkpoint.postgres.aio.AsyncPostgresSaver`）：
  与 FastAPI / SSE 事件循环兼容，不会阻塞主线程。
* **setup() 幂等**：启动时跑一次 :py:meth:`AsyncPostgresSaver.setup`，
  内部使用 ``CREATE TABLE IF NOT EXISTS``，可重复执行。
* **生命周期**：
    * :py:meth:`setup` 在 FastAPI lifespan startup 调一次，开池 + 建表
    * :py:meth:`aclose` 在 lifespan shutdown 调一次，优雅关池
    * :py:meth:`ping` 给 ``/health`` 用
* **回退**（仅 dev）：可通过 ``CHECKPOINTER_BACKEND=memory`` 切到
  :class:`langgraph.checkpoint.memory.InMemorySaver`，方便无 DB 调试。

线程/并发安全
-------------

* :class:`AsyncConnectionPool` 内部是 asyncio.Lock 保护的 FIFO 队列，
  同一 saver 可被多请求并发使用。
* 工厂本身是模块级单例（:data:`checkpointer_factory`），整个进程共享一份池。

环境变量
--------

通过 :class:`src.config.settings.Settings` 读取（见 ``.env.development``）：

* ``POSTGRES_HOST`` / ``POSTGRES_PORT`` / ``POSTGRES_USER``
  / ``POSTGRES_PASSWORD`` / ``POSTGRES_DB``
* ``POSTGRES_SCHEMA`` —— checkpointer 表所在的 schema
* ``POSTGRES_POOL_MIN_SIZE`` / ``POSTGRES_POOL_MAX_SIZE`` —— 池大小
* ``POSTGRES_POOL_TIMEOUT`` —— 获取连接超时（秒）
* ``CHECKPOINTER_BACKEND`` —— ``postgres``（默认） / ``memory``
"""

# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator, Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from psycopg import errors as pg_errors
from psycopg_pool import AsyncConnectionPool

from src.config.settings import Settings, get_settings
from src.core.schemas import Plan, Review

logger = logging.getLogger(__name__)

Backend = Literal["postgres", "memory"]

# ---------------------------------------------------------------------------
# Windows 兼容：psycopg3 async 必须用 SelectorEventLoop。
# ``asyncio.set_event_loop_policy`` 在 Python 3.16 将被移除，
# 推荐用 uvicorn ``loop_factory=``（见 ``src/__main__.py``）。
# 这里保留 policy 调用作为防御层 —— 任何不走 uvicorn 的入口
# （脚本、jupyter）依然能拿到正确的 loop。warnings filter 把
# 3.14 上的 DeprecationWarning 吞掉，避免污染启动日志。
# ---------------------------------------------------------------------------
if sys.platform == "win32":  # pragma: no cover —— 仅 Windows 路径
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except AttributeError:  # 极老 Python 不存在该 policy
            pass
    del warnings


def _build_conninfo(s: Settings) -> str:
    """组装 psycopg 风格的 DSN。

    * 使用 :rfc:`3986` 百分号编码的密码，避免特殊字符被 URL 解析器搞坏。
    * ``localhost`` 在 Windows + psycopg async + SelectorEventLoop 下经常
      卡住（先解析到 IPv6 ::1，连接超时回退到 IPv4）—— 我们给
      ``localhost`` / ``127.0.0.1`` 显式补一个 ``hostaddr=127.0.0.1``，
      强制走 IPv4，省掉那次双栈来回。
    * 自定义 schema 通过 ``options=-c search_path=...`` 走 PG 协议层
      ``SET search_path``，等效于每个连接都先执行 ``SET search_path``。
      这是 langgraph-checkpoint-postgres 3.x 移除了 ``schema`` 之后的
      标准做法。
    * libpq ``keepalives=1`` —— Windows 上必须显式开，libpq 默认不开。
      配合 ``keepalives_idle`` / ``keepalives_interval`` / ``keepalives_count``
      在 TCP 层探测已被防火墙 / NAT 静悄悄 drop 的死连接。否则池子里的
      僵尸连接要等到下一次 ``execute`` 才暴露，已经太晚。
    """
    from urllib.parse import quote, quote_plus

    base = (
        f"postgresql://{quote_plus(s.POSTGRES_USER)}:"
        f"{quote_plus(s.POSTGRES_PASSWORD)}@"
        f"{s.POSTGRES_HOST}:{s.POSTGRES_PORT}/"
        f"{quote_plus(s.POSTGRES_DB)}"
    )
    params: list[str] = []
    if s.POSTGRES_HOST in ("localhost", "127.0.0.1"):
        # 强制 IPv4，绕开 localhost -> ::1 解析抖动
        params.append("hostaddr=127.0.0.1")
    if s.POSTGRES_SCHEMA and s.POSTGRES_SCHEMA != "public":
        # 通过 PG 启动参数设置 search_path（langgraph 3.x 已不接 schema kwarg）
        # quote 后是合法的 libpq 连接参数
        sp = quote(f'-c search_path="{s.POSTGRES_SCHEMA}",public')
        params.append(f"options={sp}")
    # libpq TCP keepalive。Windows 防火墙 / NAT 经常静悄悄 RST 长连接，
    # 客户端 libpq 默认 keepalives=0（关），必须显式开才能让 OS 帮我们探测。
    if s.POSTGRES_KEEPALIVES:
        params.append(f"keepalives={int(s.POSTGRES_KEEPALIVES)}")
        params.append(f"keepalives_idle={int(s.POSTGRES_KEEPALIVES_IDLE)}")
        params.append(f"keepalives_interval={int(s.POSTGRES_KEEPALIVES_INTERVAL)}")
        params.append(f"keepalives_count={int(s.POSTGRES_KEEPALIVES_COUNT)}")
    if params:
        base = f"{base}?{'&'.join(params)}"
    return base


async def _check_connection_health(conn) -> None:
    """池子 ``check`` 钩子：每次 ``getconn`` 前跑 ``SELECT 1`` 验活。

    抛任何异常（连接被服务端 kick、TCP 断、查询超时）都视为"坏连接"，
    psycopg-pool 会丢弃并自动重建。这是防"僵尸连接"导致 PoolTimeout
    的**第一道防线**。

    SELECT 1 走 PG 内部 ping path，**不**触发应用级查询计划，开销 < 1ms。
    """
    await conn.execute("SELECT 1")


# ---------------------------------------------------------------------------
# 消息类型 helper
# ---------------------------------------------------------------------------
def _is_human_message(msg: object) -> bool:
    """判断一条 LangChain ``BaseMessage`` 是否是 human / user 消息。

    不直接 ``isinstance`` 导入具体类（避免拉一票 ``langchain_core`` 进来），
    而是认类名 —— checkpointer 序列化 / 反序列化时会还原成 ``HumanMessage``，
    但我们只需要 role 标签，类名判定已经够稳。
    """
    cls_name = type(msg).__name__
    return cls_name in {"HumanMessage", "HumanMessageChunk"}


def _extract_text(content: object) -> str:
    """把 LangChain ``BaseMessage.content`` 归一化成纯文本。

    * ``str`` 直接返回
    * ``list[dict]``（多模态 / content blocks）只取 ``type == "text"`` 的片段
    * 其它：``str(content)`` 兜底
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for p in content:
            if isinstance(p, dict):
                if p.get("type") == "text" and isinstance(p.get("text"), str):
                    parts.append(p["text"])
            elif isinstance(p, str):
                parts.append(p)
        return "".join(parts)
    return str(content) if content is not None else ""


class CheckpointerFactory:
    """单例工厂：管理连接池 + saver 生命周期。

    使用::

        factory = CheckpointerFactory(settings)
        await factory.setup()        # 启动时调一次
        saver = factory.saver        # 编译 LangGraph 时直接用
        await factory.ping()         # 健康检查
        await factory.aclose()       # 关闭时调一次
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings: Settings = settings or get_settings()
        self._pool: AsyncConnectionPool | None = None
        self._saver: BaseCheckpointSaver | None = None
        self._backend: Backend = self._settings.CHECKPOINTER_BACKEND  # type: ignore[assignment]
        if self._backend not in ("postgres", "memory"):
            raise ValueError(f"不支持的 CHECKPOINTER_BACKEND={self._backend!r}，可选：postgres | memory")

    # ------------------------------------------------------------------ #
    # 生命周期
    # ------------------------------------------------------------------ #
    async def setup(self) -> None:
        """开池 + 建表。幂等：可重复调。

        Raises
        ------
        RuntimeError
            DB 不可达 / 鉴权失败 / DDL 执行失败
        """
        if self._saver is not None:
            logger.debug("CheckpointerFactory 已初始化，跳过 setup()")
            return

        if self._backend == "memory":
            from langgraph.checkpoint.memory import InMemorySaver

            logger.warning("CHECKPOINTER_BACKEND=memory —— 状态不会持久化，重启即丢失，仅用于本地无 DB 调试。")
            self._saver = InMemorySaver()
            return

        s = self._settings
        conninfo = _build_conninfo(s)
        logger.info(
            "初始化 Postgres 连接池：host=%s port=%d db=%s schema=%s "
            "min_size=%d max_size=%d timeout=%.1fs "
            "check=%s max_idle=%.0fs max_lifetime=%.0fs keepalives=%d",
            s.POSTGRES_HOST,
            s.POSTGRES_PORT,
            s.POSTGRES_DB,
            s.POSTGRES_SCHEMA,
            s.POSTGRES_POOL_MIN_SIZE,
            s.POSTGRES_POOL_MAX_SIZE,
            s.POSTGRES_POOL_TIMEOUT,
            s.POSTGRES_POOL_CHECK,
            s.POSTGRES_POOL_MAX_IDLE,
            s.POSTGRES_POOL_MAX_LIFETIME,
            s.POSTGRES_KEEPALIVES,
        )

        # 显式 open=False + 手动 open —— 这样 setup() 失败时能立刻 raise，
        # 比 async with 在错误路径上吞掉更安全。
        # langgraph-checkpoint-postgres 3.1.0 移除了 schema kwarg；
        # 自定义 schema 已通过 DSN 的 options=-c search_path=... 实现。
        #
        # 三道防僵尸连接配置：
        #   * check=...           —— 每次 getconn 前 SELECT 1，坏连接丢弃重建
        #   * max_idle=...        —— 闲置超过 N 秒主动关掉（防服务端超时）
        #   * max_lifetime=...    —— 强制 N 秒后重建（无论是否闲置）
        # 关掉任何一道都把"防僵尸"的责任上移到调用方，不推荐。
        self._pool = AsyncConnectionPool(
            conninfo=conninfo,
            min_size=s.POSTGRES_POOL_MIN_SIZE,
            max_size=s.POSTGRES_POOL_MAX_SIZE,
            timeout=s.POSTGRES_POOL_TIMEOUT,
            kwargs={"autocommit": True},  # langgraph 自己管事务
            check=_check_connection_health if s.POSTGRES_POOL_CHECK else None,
            max_idle=s.POSTGRES_POOL_MAX_IDLE,
            max_lifetime=s.POSTGRES_POOL_MAX_LIFETIME,
            open=False,
        )
        try:
            await self._pool.open(wait=True, timeout=s.POSTGRES_POOL_TIMEOUT)
        except Exception as exc:
            await self._safe_close_pool()
            raise RuntimeError(
                f"无法连接到 PostgreSQL ({s.POSTGRES_HOST}:{s.POSTGRES_PORT}/"
                f"{s.POSTGRES_DB})：{type(exc).__name__}: {exc}"
            ) from exc

        # 若用了自定义 schema，预先 CREATE SCHEMA（连接走的是 default search_path，
        # 需要切到目标 schema 跑一次 DDL，之后 langgraph 自己的 search_path 才生效）。
        if s.POSTGRES_SCHEMA and s.POSTGRES_SCHEMA != "public":
            try:
                async with self._pool.connection() as conn:
                    await conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{s.POSTGRES_SCHEMA}"')
            except pg_errors.InsufficientPrivilege:
                logger.warning(
                    "当前用户无权 CREATE SCHEMA，继续使用 schema=%s（请 DBA 预创建）",
                    s.POSTGRES_SCHEMA,
                )

        self._saver = AsyncPostgresSaver(self._pool)

        try:
            await self._saver.setup()
        except Exception as exc:
            await self._safe_close_pool()
            raise RuntimeError(f"checkpointer.setup() 失败：{type(exc).__name__}: {exc}") from exc

        logger.info("AsyncPostgresSaver 就绪 (schema=%s)", s.POSTGRES_SCHEMA)

    async def aclose(self) -> None:
        """关池。幂等：多次调安全。"""
        await self._safe_close_pool()
        self._saver = None
        logger.info("CheckpointerFactory 已关闭")

    async def _safe_close_pool(self) -> None:
        if self._pool is not None:
            try:
                await self._pool.close()
            except Exception:  # pragma: no cover —— 关池失败不致命
                logger.exception("关闭连接池时出错（忽略）")
            self._pool = None

    # ------------------------------------------------------------------ #
    # 业务接口
    # ------------------------------------------------------------------ #
    @property
    def saver(self) -> BaseCheckpointSaver:
        """已就绪的 saver 引用。必须先 :py:meth:`setup`。

        编译 LangGraph 时直接 ``g.compile(checkpointer=factory.saver)``。
        """
        if self._saver is None:
            raise RuntimeError(
                "CheckpointerFactory 尚未 setup()。请在 FastAPI lifespan startup 中先 await factory.setup()。"
            )
        return self._saver

    @property
    def backend(self) -> Backend:
        return self._backend

    async def ping(self) -> dict:
        """健康检查：池活跃度 + 一次 ``SELECT 1``。

        暴露的 stats 让我们**一眼分辨**三种常见故障：

        * 正常：
          ``size > 0, available > 0, requests_num == 0``，``ok: true``
        * 池子打满（并发耗尽）：
          ``size == max_size, available == 0, requests_num > 0``，``ok: true`` 但要警惕
        * 全是僵尸（坏连接）：
          ``SELECT 1`` 抛 ``OperationalError``，``ok: false`` + ``error`` 字段

        Returns
        -------
        dict
            ``{"ok": bool, "backend": str, "pool": {...}}``
        """
        info: dict = {"ok": False, "backend": self._backend}
        if self._backend == "memory":
            info["ok"] = True
            info["pool"] = {"backend": "memory"}
            return info
        if self._pool is None:
            info["error"] = "pool not initialized"
            return info
        try:
            async with self._pool.connection() as conn:
                await conn.execute("SELECT 1")
            stats = self._pool.get_stats()
            info["ok"] = True
            info["pool"] = {
                # 关键诊断字段
                "min_size": self._pool.min_size,
                "max_size": self._pool.max_size,
                "size": stats.get("pool_size"),
                "available": stats.get("pool_available"),
                "requests_num": stats.get("requests_num"),
                "requests_wait_ms": stats.get("requests_wait_ms"),
                # 次要：累计统计
                "connections_num": stats.get("connections_num"),
                "connections_lost": stats.get("connections_lost"),
                "usage_ms": stats.get("usage_ms"),
            }
        except Exception as exc:
            info["error"] = f"{type(exc).__name__}: {exc}"
        return info

    # ------------------------------------------------------------------ #
    # Thread 历史 / 列表 / 删除 —— AG-UI ``/threads/*`` 端点的数据源
    # ------------------------------------------------------------------ #
    async def get_thread_state(self, thread_id: str) -> dict | None:
        """读取指定 ``thread_id`` 的最新 checkpoint 状态。

        Returns
        -------
        dict | None
            ``None`` 表示该 thread 不存在（从未写入过 checkpoint）。
            否则::

                {
                    "thread_id": str,
                    "checkpoint_id": str,
                    "ts": str,                    # ISO8601
                    "messages": list[BaseMessage],
                    "channel_values": dict,       # 完整 state（plan / review / ...）
                    "metadata": dict,
                }
        """
        if self._saver is None:
            raise RuntimeError("CheckpointerFactory 尚未 setup()。")
        if self._backend == "memory":
            # 内存模式只支持同步查
            cfg = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
            cp = self._saver.get_tuple(cfg)  # type: ignore[attr-defined]
        else:
            cfg = {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": "",
                }
            }
            cp = await self._saver.aget_tuple(cfg)
        if cp is None:
            return None
        return {
            "thread_id": thread_id,
            "checkpoint_id": cp.checkpoint["id"],
            "ts": cp.checkpoint.get("ts", ""),
            "messages": cp.checkpoint["channel_values"].get("messages", []) or [],
            "channel_values": dict(cp.checkpoint["channel_values"]),
            "metadata": dict(cp.metadata or {}),
        }

    async def list_threads(
        self,
        *,
        limit: int = 100,
        max_scan: int = 1000,
    ) -> list[dict]:
        """列出所有 thread（每个 thread 取最新 checkpoint 的元信息）。

        实现说明
        --------
        ``saver.alist`` 不支持按 thread 聚合 / 排序，
        所以策略是：先按时间倒序扫一批 checkpoint（``max_scan`` 控制上限），
        在 Python 端去重 ``thread_id`` 保留首次出现的（即最新）。
        适合典型量级（百级 thread），如果以后需要支持万级，再切到
        直接走 ``self._pool`` 跑 SQL。

        Returns
        -------
        list[dict]
            ``[{"thread_id", "checkpoint_id", "ts", "message_count",
                "first_user_message"}]``
        """
        if self._saver is None:
            raise RuntimeError("CheckpointerFactory 尚未 setup()。")
        if self._backend == "memory":
            return []  # 内存模式无法枚举

        out: list[dict] = []
        seen: set[str] = set()
        # alist 不带 config 就是「全部 thread、所有 checkpoint」
        # 默认按时间倒序
        async for cp in self._saver.alist(None, limit=max_scan):
            tid = (cp.config.get("configurable") or {}).get("thread_id")
            if not tid or tid in seen:
                continue
            seen.add(tid)
            msgs = (cp.checkpoint.get("channel_values") or {}).get("messages") or []
            first_user = next(
                (_extract_text(m.content) for m in msgs if _is_human_message(m)),
                None,
            )
            out.append(
                {
                    "thread_id": tid,
                    "checkpoint_id": cp.checkpoint["id"],
                    "ts": cp.checkpoint.get("ts", ""),
                    "message_count": len(msgs),
                    "first_user_message": first_user,
                }
            )
            if len(out) >= limit:
                break
        return out

    async def delete_thread(self, thread_id: str) -> bool:
        """删除一个 thread 的所有 checkpoint + writes。

        Returns
        -------
        bool
            ``True`` 表示至少删除了一个 checkpoint；``False`` 表示 thread 不存在
            或后端不支持（memory 模式）。
        """
        if self._saver is None:
            raise RuntimeError("CheckpointerFactory 尚未 setup()。")
        if self._backend == "memory":
            return False
        # 先确认存在
        cfg = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
        existing = await self._saver.aget_tuple(cfg)
        if existing is None:
            return False
        await self._saver.adelete_thread(thread_id)
        logger.info("已删除 thread: %s", thread_id)
        return True

    @asynccontextmanager
    async def lifespan(self) -> AsyncIterator[None]:
        """FastAPI lifespan 一体化包装::

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            async with checkpointer_factory.lifespan():
                yield
        """
        await self.setup()
        try:
            yield
        finally:
            await self.aclose()


# ---------------------------------------------------------------------------
# 模块级单例（导入即用，跨模块共享同一份池）
# ---------------------------------------------------------------------------
checkpointer_factory = CheckpointerFactory()

__all__ = ["CheckpointerFactory", "checkpointer_factory"]
