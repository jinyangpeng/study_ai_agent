/**
 * AG-UI 模块对外类型
 *
 * 注意：早期 ``createAguiAdapter`` / ``AguiAdapterOptions``（基于
 * assistant-ui ``ChatModelAdapter`` 旧 API）已删除 —— 整个项目统一走
 * :func:`useChatController` （基于 ``useExternalStoreRuntime``），
 * 如需外部脚本对接，参考 ``useChatController`` 的入参构造请求。
 */
import type { AguiStateSnapshot } from './events';
export type { AguiStateSnapshot };
