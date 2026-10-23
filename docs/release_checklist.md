# Atlas-X Cursor Studio 发布检查清单

## 基础功能

- [ ] 应用可以正常启动
- [ ] 托盘图标显示正常
- [ ] 主窗口可以从托盘打开与隐藏
- [ ] 至少 10 个内置鼠标主题可预览并切换
- [ ] 主题配色可分别调整主体色、描边色、强调色、发光色
- [ ] 找回鼠标快捷键可通过录制框设置并正常触发
- [ ] 快速晃动鼠标后可显示尾迹提示
- [ ] 全局光标大小设置可影响当前内置主题
- [ ] 点击波纹可正常触发
- [ ] 高亮层可在多屏环境中定位当前鼠标
- [ ] 自定义图片可导入、预览、自动抠图
- [ ] 自定义 `.cur` 光标可生成并应用
- [ ] 按程序切换主题规则可生效
- [ ] 动态光标可正常播放
- [ ] 恢复系统默认光标可用
- [ ] 配置重启后仍然保留
- [ ] 损坏的 JSON 配置有原始备份，应用可使用默认配置启动
- [ ] 保存配置失败后原配置仍可读取
- [ ] 普通用户从只读安装目录运行时，缩放和动态光标缓存仍可生成
- [ ] 更换到已被占用的快捷键时，原快捷键仍可使用且不保存失败设置
- [ ] 自动抠图期间界面可响应，重复操作被阻止，失败后可重试
- [ ] 自动抠图期间退出会等待任务结束，线程不会被提前销毁
- [ ] 模型下载超时或校验失败后，原模型文件保留且临时文件清理
- [ ] 带 EXIF 方向的图片导入方向正确，透明 PNG 抠图不恢复透明区域

## 系统集成

- [ ] 开机启动设置可写入并可取消
- [ ] 退出应用时状态符合预期
- [ ] 异常退出后不会长期残留异常光标
- [ ] 全屏自动暂停增强验证完成
- [ ] 多显示器环境验证完成
- [ ] DPI 缩放环境验证完成

## 打包与发布

- [ ] `scripts/build.ps1` 可执行
- [ ] `atlas_cursor_studio.spec` 可生成产物
- [ ] `dist\\AtlasXCursorStudio\\AtlasXCursorStudio.exe` 可启动
- [ ] `scripts\\build_release.ps1` 可生成完整发布包
- [ ] `release\\AtlasXCursorStudio-portable.zip` 已生成
- [ ] `release\\AtlasXCursorStudio-Setup-1.0.exe` 已生成
- [ ] 发布目录包含必要 DLL 和资源文件
- [ ] 首次抠图时模型下载行为符合预期

## 文档

- [ ] README 可指导他人完成安装和运行
- [ ] 发布指南可指导打包、上传和回归检查
- [ ] 已实现功能说明与实际行为一致


## 软著与权属

- [ ] README、LICENSE、Release 文案中的著作权人均为张希
- [ ] 软件正式产品名称均为 Atlas-X Cursor Studio
- [ ] 软著登记全称均为 Atlas-X Cursor Studio 鼠标指针自定义工具软件 V1.0
- [ ] GitHub 仓库首页截图已保存
- [ ] GitHub 提交记录截图已保存
- [ ] GitHub Release 页面截图已保存
- [ ] GitHub LICENSE 页面截图已保存
- [ ] `assets/app_icon.ico` 已按项目生成资产记录
- [ ] `assets/builtin_cursors` 下 png/cur 已按项目生成资产记录

- [ ] 发布包包含 `THIRD_PARTY_NOTICES.md`
- [ ] 发布包包含 `licenses` 目录
- [ ] `licenses` 目录包含 LGPL-3.0、GPL-3.0、PySide6/Qt for Python 和 Qt 第三方许可说明
- [ ] README 和软件关于页包含 PySide6 / Qt for Python LGPLv3 路径说明
