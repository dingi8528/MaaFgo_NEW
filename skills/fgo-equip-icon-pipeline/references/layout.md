# 目录与转换规则

默认解包资源根目录：`F:\\Game_AUTO\\MaaFGO\\FGO整包\\图标_游戏内显示`。

| 用途 | 源与转换 | 高价值源 | 当前工程部署目录 |
|---|---|---|---|
| list（仓库识别） | `Faces` 128×128 RGBA → Bilinear 158×158 → FASTOCTREE 256 色无抖动 → 左裁 11、上裁 27、下裁 75 | `Faces_礼装_158_256色无抖动_上裁27左裁11下裁75_仓库界面识别用_高价值礼装`，147×56 P | `assets/resource/base/image/EquipFaces/list` |
| team（编队识别） | `EquipFaces_188` → 左右各裁 18 → 垂直居中保留 86 → FASTOCTREE 256 色无抖动 | `EquipFaces_188_左右裁18_上下居中保留86_256色无抖动_编队用_高价值礼装`，152×86 P | `assets/resource/base/image/EquipFaces/team` |

筛选表：`F:\\KumikoPythonCode\\FGO主线剧情epub\\equip_list.xlsx`。必需列为 `equipId`、`非高价值礼装`。

list 完整中间目录为 `Faces_礼装_158_256色无抖动_上裁27左裁11下裁75_仓库界面识别用`。team 完整中间目录为 `EquipFaces_188_左右裁18_上下居中保留86_256色无抖动_编队用`。
