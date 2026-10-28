# Atlas-X Cursor Studio 发布指南

## 版本与权属

- 软件正式产品名称：Atlas-X Cursor Studio
- 软著登记全称：Atlas-X Cursor Studio 鼠标指针自定义工具软件 V1.0
- 软件简称：Atlas-X Cursor Studio
- 著作权人：张希
- 开发完成日期：2026-04-21
- 首次发表日期：2026-04-21
- 首次发表地点：GitHub 网络发布

## 建议发布件

- 安装器：`release\1.0.1\AtlasXCursorStudio-Setup-1.0.1.exe`
- 便携版：`release\1.0.1\AtlasXCursorStudio-portable-1.0.1.zip`
- 校验文件：`release\1.0.1\SHA256SUMS.txt`
- 发布包建议包含 `THIRD_PARTY_NOTICES.md` 和 `licenses` 目录。

## 构建与发布

1. 更新 `core/constants.py` 中的 `APP_VERSION`、README 下载链接和 `docs/releases/v版本号.md`。
2. 运行 `python -m pytest -q` 与 `python -m compileall -q app core services ui tests`。
3. 运行 `scripts/build_release.ps1 -Clean`。脚本自动从版本常量读取版本，构建到独立目录，运行打包程序 `--self-test`，然后生成便携版、安装器和 SHA-256 校验文件。
4. 自检覆盖资源、配置读写、光标生成、主窗口和 ONNX 导入，不注册系统快捷键、不修改开机启动、不替换系统光标，不下载模型。
5. 将变更提交并推送，随后推送同名标签（例如 `v1.0.1`）。GitHub Actions 自动执行测试和打包，先上传为草稿，资产齐备后发布为 Latest。已公开版本不会被工作流覆盖。
6. 在 Releases 确认可下载的 `.exe`、`.zip` 和 `SHA256SUMS.txt`，核对版本和校验值。多屏、DPI、全屏等行为仍需要实机验证。

当前发布说明见 [v1.0.1](releases/v1.0.1.md)。旧版首次发表信息保留如下，不能用新版本截图替代旧版证据。

## v1.0 首次发表文案（历史记录）

标题：`Atlas-X Cursor Studio v1.0`

```text
Atlas-X Cursor Studio v1.0 发布。

软件正式产品名称：Atlas-X Cursor Studio
软著登记全称：Atlas-X Cursor Studio 鼠标指针自定义工具软件 V1.0
著作权人：张希
首次发表日期：2026-04-21

本版本包含：托盘常驻、内置鼠标主题、配色自定义、找回鼠标高亮、晃动尾迹、点击波纹、自定义图片转 .cur 光标、按程序切换主题、动态光标、全屏自动暂停增强、开机启动控制。

第三方组件说明：本软件使用 PySide6 / Qt for Python 构建桌面界面。PySide6 Community Edition 按 LGPLv3 路径使用。第三方组件许可证见项目 THIRD_PARTY_NOTICES.md 或发布包 licenses 目录。首次使用自动抠图时可能下载第三方 u2net.onnx 模型，该模型仅作为可选运行资源使用，不属于本项目原创源码。
```

保留 v1.0 在 2026-04-21 的原始公开发表证据；后续版本的日期以各自的发布记录为准。

## 第三方组件与 PySide6 合规口径

本软件使用 PySide6 Community Edition，并按 LGPLv3 路径履行许可义务。本软件未选择 PySide6 的 GPL 授权路径，项目自身代码不因使用 PySide6 而改用 GPL。本项目未修改 PySide6、Qt、Shiboken 源码。PySide6、Qt、Shiboken 及其相关组件不作为张希的原创源码提交。PySide6 用于 Qt 桌面界面、窗口控件、托盘和覆盖层窗口。第三方依赖仅作为运行依赖或构建依赖使用，不纳入软著原创源程序鉴别材料。自动抠图模型为第三方模型文件，仅作为可选运行资源使用，不纳入张希原创源程序鉴别材料。

发布包建议新增 `licenses` 目录，放置：

- `LGPL-3.0.txt`
- `GPL-3.0.txt`
- PySide6 或 Qt for Python 许可说明
- Qt 第三方许可说明
- `THIRD_PARTY_NOTICES.md`

如后续进行严格商业闭源分发、企业部署、应用商店上架或无法满足 LGPLv3 要求，应重新评估 Qt for Python 商业授权。
