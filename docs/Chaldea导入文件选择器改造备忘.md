# Chaldea 队伍导入：文件选择器改造备忘

状态：暂缓实施。当前打包版及任务选项保持原样，不应只修改任务 JSON 就宣称功能已生效。

## 期望行为

战斗任务中的「Chaldea 队伍导入」点击文件按钮时，默认打开软件目录下的 `config/Battle`，文件类型默认筛选 `.json`。用户仍可在同一输入框手动填写 Chaldea 分享链接、队伍 ID、关卡 ID 或本地文件路径；已保存的输入值和导入逻辑不变。`config/Battle` 尚不存在时，文件对话框退回到软件目录。

## 当前限制

任务选项的 `input_type: "file"` 只能让 MXU 显示文件按钮，不能配置对话框的起始目录或文件类型。MXU 的 `src/components/FormControls.tsx` 中，`FileInput` 调用 `open({ multiple: false, filters })`，默认筛选为可执行文件和所有文件。`src/components/OptionEditor.tsx` 没有向它传递任务级目录或筛选配置。任务 JSON 的 `default` 是输入值，不能用它设置文件对话框位置。

## 实施步骤

1. 在 MXU 源码 `src/types/interface.ts` 的 `InputItem` 中增加可选字段：`file_dialog_dir?: string`（相对于 `interface.json` 所在目录）和 `file_dialog_filters?: { name: string; extensions: string[] }[]`。
2. 在 `src/components/OptionEditor.tsx` 的 `input_type === 'file'` 分支，把这两个字段以及已有的项目根路径 `basePath` 传给 `FileInput`。
3. 在 `src/components/FormControls.tsx` 的 `FileInput` 中，仅当设置了相对目录时，用 Tauri 路径 API 将其与 `basePath` 拼成绝对路径，再作为 `open()` 的 `defaultPath`；目录不存在时回退到 `basePath`。优先使用选项指定的 `filters`，未指定时保留现有通用筛选。选中后的绝对路径仍写回输入框，以兼容现有导入脚本。
4. MXU 客户端支持这些字段后，在 MaaFGO 的 `assets/options/Chaldea导入手动输入.json` 和 `assets/options/chaldea_team_config.json` 的 `chaldea_import_source` 输入项中加入：

   ```json
   "file_dialog_dir": "config/Battle",
   "file_dialog_filters": [{"name": "JSON", "extensions": ["json"]}]
   ```

5. 同步更新 MaaFGO 的 `deps/tools/interface.schema.json` 中 `inputItem` 的字段定义，否则资源校验会将新增字段判为未知属性。
6. 验证 MXU 前端构建、MaaFGO 选项 Schema、首次运行（目录不存在）、已有缓存文件、手动输入链接/ID，以及两个 Chaldea 导入入口。重新编译 MXU 后才能让打包版按钮生效；同步打包版前遵循项目的差异比较、备份和哈希校验约定，不覆盖 `interface.json` 的版本号。

只改 MaaFGO 的选项文件不会改变当前打包版的按钮行为，因此本备忘未提前加入上述配置字段。
