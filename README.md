# Atlas-X Cursor Studio

Atlas-X Cursor Studio 是一个面向 Windows 的托盘常驻鼠标增强工具，用来让鼠标更容易被看见、更方便切换主题，也更适合多屏、演示和复杂桌面场景。

当前版本：`1.0`

## 软著登记信息

- 软件正式产品名称：Atlas-X Cursor Studio
- 软著登记全称：Atlas-X Cursor Studio 鼠标指针自定义工具软件 V1.0
- 软件简称：Atlas-X Cursor Studio
- 著作权人：张希
- 开发完成日期：2026-04-21
- 首次发表日期：2026-04-21
- 首次发表地点：GitHub 网络发布

本软件正式产品名称为 Atlas-X Cursor Studio。软著登记全称为“Atlas-X Cursor Studio 鼠标指针自定义工具软件 V1.0”，其中“鼠标指针自定义工具软件”为功能描述，“V1.0”为登记版本号。

## 它能做什么

- 一键切换和恢复系统鼠标主题
- 提供 10 套内置主题，并支持主体色、描边色、强调色、发光色分别调整
- 快捷键找回鼠标位置
- 快速晃动鼠标时显示尾迹提示
- 鼠标点击时显示波纹反馈
- 调整内置主题的全局光标大小
- 导入图片并生成可用的 `.cur` 光标
- 按前台程序自动切换主题
- 播放内置动态光标
- 全屏应用时自动暂停增强效果
- 托盘常驻、配置持久化、开机启动控制

## 下载与使用

推荐优先使用发布页中的这两种文件：

- 安装器：`AtlasXCursorStudio-Setup-1.0.exe`
- 便携版：`AtlasXCursorStudio-portable.zip`

普通用户优先下载安装器。  
如果不想安装，可以下载便携版，解压后直接运行。

## 使用前说明

- 支持系统：Windows 10 / 11
- 首次运行不需要管理员权限
- 首次使用自动抠图时，程序可能会联网下载第三方 `u2net.onnx` 模型；该模型仅作为可选运行资源使用，不属于本项目原创源码
- 某些全屏游戏、远程桌面或自行接管光标的程序，可能会覆盖增强效果

## 主要功能说明

### 1. 找回鼠标

可以录制一个全局快捷键，在任何时候快速高亮当前鼠标位置。

### 2. 内置主题

内置多套鼠标主题，可预览、应用、恢复默认，并且支持分别调整多种颜色层。

### 3. 自定义光标

可以导入普通图片，自动抠图、裁边、缩放并设置热点，最后生成可应用的 `.cur` 光标。

### 4. 点击与移动反馈

支持点击波纹，以及快速晃动鼠标时的尾迹提示，方便快速重新定位鼠标。

### 5. 按程序切换主题

可以根据前台进程名自动切换主题，例如：

```text
powerpnt.exe = highlight_arrow
```

### 6. 动态光标与全屏暂停

支持内置主题动态播放，并可在检测到全屏应用时自动暂停增强效果，减少干扰。

## 可靠性与数据存储

- 配置、日志、自定义光标和生成的主题缓存存放在 `%APPDATA%\atlas_x_cursor_studio`，不向安装目录写入缓存；目录不可用时尝试 `%LOCALAPPDATA%`，然后是用户主目录下的 `.atlas_x_cursor_studio`。
- 配置保存使用同目录临时文件和原子替换。JSON 损坏时先保留 `config.json.corrupt-*.bak` 原始备份，再使用默认配置启动；未知字段会被忽略，错误类型和越界参数会回退或限制到有效范围。
- 自动抠图在后台执行，界面仍可响应。处理期间会禁用图片编辑按钮，退出请求会等待当前任务结束，避免中断写入或销毁正在运行的线程。
- 模型下载设置 30 秒连接/读取超时，先下载到临时文件并校验，再替换缓存；下载中断或校验失败不会覆盖原有模型文件。
- 更换全局快捷键时先注册新快捷键，成功后才释放旧快捷键；冲突时保留原快捷键和原设置。
- 图片导入会应用 EXIF 方向，抠图保留原有透明度，预览使用实际生成光标的像素几何。

## 已知限制

- 某些程序会自行接管系统光标，可能覆盖 Atlas-X Cursor Studio 的效果
- 动态光标当前只对内置主题生效
- 自定义光标的“全局光标大小”最佳效果依赖重新生成光标文件
- 如果只分发单个 `AtlasXCursorStudio.exe`，程序无法完整运行；必须使用安装器、便携版，或整个 `dist\AtlasXCursorStudio` 目录

## 开发者说明

如果你是来查看源码、构建或二次开发，可以从这里开始。

### 环境

- Python 3.11+
- 建议使用 64 位 Python

### 安装依赖

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 源码运行

```powershell
python -m app.main
```

### 打包

```powershell
.\scripts\build.ps1
```

完整发布：

```powershell
.\scripts\build_release.ps1
```

预期产物：

- `dist\AtlasXCursorStudio\AtlasXCursorStudio.exe`
- `release\AtlasXCursorStudio-portable.zip`
- `release\AtlasXCursorStudio-Setup-1.0.exe`

### 测试

```powershell
python -m pytest -q
python -m compileall -q app core services ui tests
```

测试仅收集 `tests/`，使用临时用户数据、离屏 Qt 界面和模拟系统接口，不修改真实系统光标、注册表或全局快捷键，也不会下载 U2Net 模型。GitHub Actions 在 Windows 上运行 Python 3.11 / 3.13 两组检查。

若本机旧 pytest 临时目录出现访问权限错误，可使用全新目录运行，不需要修改旧目录权限：

```powershell
$testRunDir = Join-Path $PWD ('configs\runtime\verification-' + [guid]::NewGuid().ToString('N'))
python -m pytest -q --basetemp $testRunDir
```

真实托盘、系统光标切换、多屏/DPI 和安装包仍需按发布检查清单进行桌面验证。

### 项目结构

```text
app/
core/
services/
ui/
assets/
configs/
scripts/
tests/
docs/
```

更详细的发布检查可以看 [docs/release_guide.md](./docs/release_guide.md) 和 [docs/release_checklist.md](./docs/release_checklist.md)。

## License

This project is licensed under the MIT License. Copyright (c) 2026 张希. See [LICENSE](./LICENSE).

## Third-Party Components

本软件使用 PySide6 / Qt for Python 构建桌面界面。PySide6 Community Edition 按 LGPLv3 路径使用。本软件未选择 PySide6 的 GPL 授权路径，项目自身代码不因使用 PySide6 而改用 GPL。

本项目未修改 PySide6、Qt、Shiboken 源码。PySide6、Qt、Shiboken 及其相关组件不作为张希的原创源码提交。第三方组件许可证见项目 [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md) 或发布包 `licenses` 目录。
