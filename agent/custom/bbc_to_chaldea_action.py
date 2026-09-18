"""将 BBC 队伍配置转换为原生战斗可读取的本地 Chaldea JSON。"""

import os
import sys

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

import mfaalog

_AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _AGENT_DIR not in sys.path:
    sys.path.insert(0, _AGENT_DIR)

from chaldea.bbc_importer import BbcImportError, import_bbc_file


@AgentServer.custom_action("import_bbc_to_chaldea")
class ImportBbcToChaldea(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        try:
            node = context.get_node_data(argv.node_name) or {}
            attach = node.get("attach") or {}
            source = str(attach.get("bbc_source_config") or "").strip()
            output, warnings = import_bbc_file(source)
            for warning in warnings:
                mfaalog.warning(f"[BBC→Chaldea] {warning}")
            mfaalog.info(f"[BBC→Chaldea] 已生成本地队伍: {output}")
            mfaalog.info(f"[BBC→Chaldea] 在 Chaldea 队伍导入中填写: {output.name}")
            return CustomAction.RunResult(success=True)
        except (BbcImportError, OSError) as exc:
            mfaalog.error(f"[BBC→Chaldea] 导入失败: {exc}")
            return CustomAction.RunResult(success=False)
