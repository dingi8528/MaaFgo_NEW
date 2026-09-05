---
name: fgo-equip-icon-pipeline
description: 更新 MaaFGO 礼装图标资源：按礼装配置筛选高价值项，必要时从 Atlas Academy 补齐 Faces，生成 list、team 识别图，并部署到工程资源目录。适用于 MaaFGO 礼装图标更新；不用于从者头像或 UI 图标。
---

# FGO 礼装图标流水线

将礼装资源同步到当前工程的仓库识别（`list`）和编队识别（`team`）目录。默认以 `equip_list.xlsx` 的 `非高价值礼装=0` 筛选高价值礼装。

## 工作流

1. 阅读 [目录与规则](references/layout.md)，确认源目录、配置表和目标目录。
2. 先以只读方式清点源图、配置和目标目录差异。
3. 有高价值礼装缺图时，先从 Atlas Academy 补入 `Faces` 初始目录，校验为 128×128 RGBA PNG 后再生成。
4. 依照 list 或 team 转换规则生成完整识别资源，筛选高价值礼装，并同步到工程目标目录。
5. 结束前校验文件数、文件名集合、尺寸、颜色模式与 SHA-256。

使用 `scripts/sync_equip_icons.py`；先执行 `--dry-run`，确认差异后再执行写入操作。

## 约束

- 文件名必须为 `f_<equipId>0.png`；Excel 的 `equipId` 先规范化为整数文本，`非高价值礼装` 接受数值 `0` 或文本 `"0"`。
- 最终部署目标仅为当前工程内的 `assets/resource/base/image/EquipFaces/list` 与 `assets/resource/base/image/EquipFaces/team`，不得写入解包目录的 `EquipFaces/list`、`EquipFaces/team`。
- 仅在目标衍生目录中清理不属于当前筛选结果的 PNG；不得删除 `Faces`、`EquipFaces` 或未筛选的 188 源目录。
- Atlas 补图 URL 为 `https://static.atlasacademy.io/JP/Faces/f_<equipId>0.png`。下载失败时列出缺失项并停止，不能使用占位图或错误礼装。
