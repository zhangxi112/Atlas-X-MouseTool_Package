"""Main application window."""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtGui import QCloseEvent, QColor, QImage, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QKeySequenceEdit,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PIL import Image

from app.bootstrap import AppContext
from core.builtin_themes import BUILTIN_THEMES, get_builtin_theme
from core.constants import APP_NAME, APP_VERSION
from core.models import CursorTheme
from services.enhancement_manager import parse_app_theme_rules, serialize_app_theme_rules
from services.image_pipeline import CursorProject
from services.tray_hotkey_manager import describe_hotkey_sequence, parse_hotkey_sequence
from ui.app_styles import apply_app_theme
from ui.background_removal import BackgroundRemovalTask
from ui.dialog_utils import pick_color, show_information, show_question, show_warning
from ui.icon_factory import create_app_icon


class WheelSafeSpinBox(QSpinBox):
    """Ignore wheel changes unless the control is focused."""

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        if self.hasFocus():
            super().wheelEvent(event)
            return
        event.ignore()


class WheelSafeSlider(QSlider):
    """Ignore wheel changes unless the control is focused."""

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        if self.hasFocus():
            super().wheelEvent(event)
            return
        event.ignore()


class MainWindow(QMainWindow):
    """Primary desktop window used to host application tabs."""

    PALETTE_PART_LABELS = {
        "primary": "主体色",
        "secondary": "描边色",
        "accent": "强调色",
        "glow": "发光色",
    }
    TRAIL_STYLE_OPTIONS = (
        ("glow", "柔光尾迹"),
        ("dash", "虚线尾迹"),
        ("comet", "彗星尾迹"),
        ("spark", "粒子尾迹"),
        ("ring", "圆环尾迹"),
    )

    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.tray_manager = None
        self._allow_close = False
        self._background_task: BackgroundRemovalTask | None = None
        self._exit_after_background = False
        self._custom_controls: list[QWidget] = []
        self.theme_assets = {asset.theme.theme_id: asset for asset in self.context.cursor_manager.list_builtin_themes()}
        self.current_custom_project: CursorProject | None = None
        self.theme_color_buttons: dict[str, QPushButton] = {}

        self.theme_list: QListWidget | None = None
        self.theme_preview_label: QLabel | None = None
        self.theme_name_label: QLabel | None = None
        self.theme_description_label: QLabel | None = None
        self.quick_theme_label: QLabel | None = None
        self.current_theme_label: QLabel | None = None
        self.current_hotkey_label: QLabel | None = None
        self.current_tray_label: QLabel | None = None
        self.current_process_label: QLabel | None = None
        self.current_runtime_label: QLabel | None = None
        self.custom_file_label: QLabel | None = None
        self.custom_bg_status_label: QLabel | None = None
        self.custom_scale_label: QLabel | None = None
        self.custom_preview_label: QLabel | None = None
        self.scale_slider: QSlider | None = None
        self.hotspot_x_spin: QSpinBox | None = None
        self.hotspot_y_spin: QSpinBox | None = None
        self.startup_checkbox: QCheckBox | None = None
        self.multi_monitor_checkbox: QCheckBox | None = None
        self.hotkey_edit: QKeySequenceEdit | None = None
        self.quick_hotkey_edit: QKeySequenceEdit | None = None
        self.home_hotkey_hint_label: QLabel | None = None
        self.settings_hotkey_hint_label: QLabel | None = None
        self.settings_hotkey_value_label: QLabel | None = None
        self.duration_spin: QSpinBox | None = None
        self.ring_size_spin: QSpinBox | None = None
        self.pointer_size_spin: QSlider | None = None
        self.pointer_size_input_spin: QSpinBox | None = None
        self.pointer_size_value_label: QLabel | None = None
        self.shake_to_find_checkbox: QCheckBox | None = None
        self.shake_distance_spin: QSlider | None = None
        self.shake_distance_input_spin: QSpinBox | None = None
        self.shake_distance_value_label: QLabel | None = None
        self.trail_style_combo: QComboBox | None = None
        self.trail_color_button: QPushButton | None = None
        self.click_ripple_checkbox: QCheckBox | None = None
        self.ripple_duration_spin: QSpinBox | None = None
        self.ripple_size_spin: QSpinBox | None = None
        self.dynamic_cursor_checkbox: QCheckBox | None = None
        self.dynamic_interval_spin: QSpinBox | None = None
        self.app_switch_checkbox: QCheckBox | None = None
        self.app_rules_edit: QTextEdit | None = None
        self.game_mode_checkbox: QCheckBox | None = None
        self.home_dark_theme_button: QPushButton | None = None
        self.home_light_theme_button: QPushButton | None = None
        self.settings_dark_theme_button: QPushButton | None = None
        self.settings_light_theme_button: QPushButton | None = None
        self.uninstall_button: QPushButton | None = None
        self._pointer_size_warning_zone: str | None = None

        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.setWindowIcon(create_app_icon())
        self.setMinimumSize(960, 720)
        self.setMaximumSize(16777215, 16777215)
        self.resize(1220, 880)
        self._build_ui()
        self._set_hotkey_widgets(self.context.config.highlight.hotkey)
        self._refresh_theme_list_selection()
        self._refresh_theme_preview()
        self._refresh_trail_color_button()
        self._refresh_state_labels()
        self._refresh_custom_labels()
        self.context.enhancement_manager.runtime_state_changed.connect(self._refresh_state_labels)

    def set_tray_manager(self, tray_manager) -> None:
        self.tray_manager = tray_manager
        self._refresh_state_labels()

    def prepare_for_exit(self) -> bool:
        if self._background_task is not None:
            self._exit_after_background = True
            self.statusBar().showMessage("正在完成自动抠图，完成后将安全退出。")
            return False
        self._allow_close = True
        self.close()
        return True

    def wait_for_background_task(self) -> None:
        if self._background_task is not None:
            self._background_task.wait()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._allow_close or self.tray_manager is None:
            if self._background_task is not None:
                self._exit_after_background = True
                event.ignore()
                return
            event.accept()
            return
        event.ignore()
        self.hide()
        if self.statusBar() is not None:
            self.statusBar().showMessage("应用已最小化到托盘。", 3000)

    def _build_ui(self) -> None:
        self.setCentralWidget(self._create_tabs())
        status_bar = QStatusBar(self)
        status_bar.showMessage(f"{APP_NAME} 已启动。")
        self.setStatusBar(status_bar)

    def _create_tabs(self) -> QWidget:
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.setUsesScrollButtons(True)
        tabs.tabBar().setDrawBase(False)
        tabs.addTab(self._build_home_page(), "首页")
        tabs.addTab(self._build_theme_page(), "主题")
        tabs.addTab(self._build_custom_page(), "自定义")
        tabs.addTab(self._build_settings_page(), "设置")
        tabs.addTab(self._build_about_page(), "关于")
        return tabs

    def _build_home_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        hero = QFrame()
        hero_layout = QVBoxLayout(hero)
        title = QLabel(APP_NAME)
        title.setStyleSheet("font-size: 28px; font-weight: 700;")
        subtitle = QLabel("Windows 托盘常驻鼠标增强工具")
        subtitle.setStyleSheet("font-size: 14px; color: #475569;")
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        layout.addWidget(hero)

        state_box = QGroupBox("当前状态")
        state_layout = QVBoxLayout(state_box)
        self.current_theme_label = QLabel()
        self.current_hotkey_label = QLabel()
        self.current_tray_label = QLabel()
        self.current_process_label = QLabel()
        self.current_runtime_label = QLabel()
        for label in (self.current_theme_label, self.current_hotkey_label, self.current_tray_label, self.current_process_label, self.current_runtime_label):
            label.setWordWrap(True)
            state_layout.addWidget(label)
        layout.addWidget(state_box)

        quick_box = QGroupBox("快捷操作")
        quick_layout = QVBoxLayout(quick_box)

        theme_row = QHBoxLayout()
        self.quick_theme_label = QLabel("快速主题切换")
        prev_theme_button = QPushButton("上一个主题")
        prev_theme_button.clicked.connect(lambda: self._cycle_theme_selection(-1))
        next_theme_button = QPushButton("下一个主题")
        next_theme_button.clicked.connect(lambda: self._cycle_theme_selection(1))
        apply_theme_button = QPushButton("应用当前选择")
        apply_theme_button.clicked.connect(self._apply_selected_theme)
        theme_row.addWidget(self.quick_theme_label, 1)
        theme_row.addWidget(prev_theme_button)
        theme_row.addWidget(next_theme_button)
        theme_row.addWidget(apply_theme_button)
        quick_layout.addLayout(theme_row)

        quick_hotkey_box = QGroupBox("快速更改找回鼠标快捷键")
        quick_hotkey_layout = QVBoxLayout(quick_hotkey_box)
        quick_hotkey_layout.addWidget(QLabel("点击录制框后直接按键，不需要手动输入。推荐 F8、Shift+F8 这类一键或双键组合。"))
        quick_hotkey_row = QHBoxLayout()
        self.quick_hotkey_edit = QKeySequenceEdit()
        self._configure_hotkey_editor(self.quick_hotkey_edit)
        record_hotkey_button = QPushButton("录制")
        record_hotkey_button.clicked.connect(lambda: self._focus_hotkey_editor(self.quick_hotkey_edit))
        apply_hotkey_button = QPushButton("应用快捷键")
        apply_hotkey_button.clicked.connect(self._apply_quick_hotkey)
        quick_hotkey_row.addWidget(self.quick_hotkey_edit, 1)
        quick_hotkey_row.addWidget(record_hotkey_button)
        quick_hotkey_row.addWidget(apply_hotkey_button)
        quick_hotkey_layout.addLayout(quick_hotkey_row)

        preset_row = QHBoxLayout()
        for preset in ("F8", "Shift+F8", "Ctrl+M"):
            preset_button = QPushButton(preset)
            preset_button.clicked.connect(lambda _checked=False, value=preset: self._set_hotkey_widgets(value))
            preset_row.addWidget(preset_button)
        preset_row.addStretch(1)
        quick_hotkey_layout.addLayout(preset_row)
        self.home_hotkey_hint_label = QLabel()
        self.home_hotkey_hint_label.setWordWrap(True)
        quick_hotkey_layout.addWidget(self.home_hotkey_hint_label)
        quick_layout.addWidget(quick_hotkey_box)

        appearance_box = QGroupBox("软件主题")
        appearance_layout = QVBoxLayout(appearance_box)
        appearance_layout.addWidget(QLabel("常用切换入口放在首页，点击后立即生效并保存。"))
        appearance_row = self._build_theme_mode_switcher(home=True)
        appearance_layout.addLayout(appearance_row)
        quick_layout.addWidget(appearance_box)

        action_row = QHBoxLayout()
        preview_button = QPushButton("测试提示效果")
        preview_button.clicked.connect(self.context.overlay_manager.trigger_find_mouse)
        restore_button = QPushButton("恢复系统默认")
        restore_button.clicked.connect(self._restore_system_default)
        action_row.addWidget(preview_button)
        action_row.addWidget(restore_button)
        action_row.addStretch(1)
        quick_layout.addLayout(action_row)
        quick_layout.addWidget(QLabel("找不到鼠标时，除了快捷键，也可以启用“快速晃动后显示尾迹”。"))

        layout.addWidget(quick_box)
        layout.addStretch(1)
        return self._wrap_scroll_page(page)
    def _build_theme_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        list_panel = QWidget()
        list_panel_layout = QVBoxLayout(list_panel)
        list_box = QGroupBox("内置鼠标样式")
        list_box.setMinimumWidth(300)
        list_layout = QVBoxLayout(list_box)
        self.theme_list = QListWidget()
        self.theme_list.setMinimumWidth(280)
        for asset in self.context.cursor_manager.list_builtin_themes():
            item = QListWidgetItem(asset.theme.name)
            item.setData(Qt.ItemDataRole.UserRole, asset.theme.theme_id)
            self.theme_list.addItem(item)
        self.theme_list.currentItemChanged.connect(self._on_theme_selection_changed)
        list_layout.addWidget(self.theme_list)
        list_hint = QLabel(f"当前共 {len(BUILTIN_THEMES)} 套主题，可拖动中间分隔条调整左右宽度。")
        list_hint.setWordWrap(True)
        list_layout.addWidget(list_hint)
        apply_button = QPushButton("应用主题")
        apply_button.clicked.connect(self._apply_selected_theme)
        list_layout.addWidget(apply_button)
        list_panel_layout.addWidget(list_box)

        right_panel = QWidget()
        right_column = QVBoxLayout(right_panel)
        preview_box = QGroupBox("预览")
        preview_layout = QVBoxLayout(preview_box)
        self.theme_preview_label = QLabel("选择主题后在这里预览")
        self.theme_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.theme_preview_label.setMinimumSize(220, 220)
        self.theme_name_label = QLabel("主题名称")
        self.theme_description_label = QLabel("主题说明")
        self.theme_description_label.setWordWrap(True)
        preview_layout.addWidget(self.theme_preview_label)
        preview_layout.addWidget(self.theme_name_label)
        preview_layout.addWidget(self.theme_description_label)
        theme_id_hint = QLabel(f"可用于按程序切换的主题 ID：{', '.join(theme.theme_id for theme in BUILTIN_THEMES)} / system_default")
        theme_id_hint.setWordWrap(True)
        preview_layout.addWidget(theme_id_hint)
        right_column.addWidget(preview_box)

        color_box = QGroupBox("主题配色")
        color_layout = QVBoxLayout(color_box)
        color_note = QLabel("可以分别调整主体、描边、强调、发光四个部分，深色和浅色背景都能单独适配。")
        color_note.setWordWrap(True)
        color_layout.addWidget(color_note)
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)
        for index, part in enumerate(("primary", "secondary", "accent", "glow")):
            label = QLabel(self.PALETTE_PART_LABELS[part])
            button = QPushButton()
            button.clicked.connect(lambda _checked=False, palette_part=part: self._pick_theme_color(palette_part))
            grid.addWidget(label, index // 2, (index % 2) * 2)
            grid.addWidget(button, index // 2, (index % 2) * 2 + 1)
            self.theme_color_buttons[part] = button
        color_layout.addLayout(grid)
        color_action_row = QHBoxLayout()
        reset_colors_button = QPushButton("恢复默认配色")
        reset_colors_button.clicked.connect(self._reset_selected_theme_palette)
        color_action_row.addWidget(reset_colors_button)
        color_action_row.addStretch(1)
        color_layout.addLayout(color_action_row)
        preview_note = QLabel("预览会按照当前配色和全局光标大小实时刷新。")
        preview_note.setWordWrap(True)
        color_layout.addWidget(preview_note)
        right_column.addWidget(color_box)
        right_column.addStretch(1)

        splitter.addWidget(list_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 7)
        splitter.setSizes([360, 760])
        layout.addWidget(splitter)
        return page
    def _build_custom_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        control_panel = QWidget()
        control_panel_layout = QVBoxLayout(control_panel)
        control_box = QGroupBox("自定义图片转光标")
        control_box.setMinimumWidth(320)
        control_layout = QVBoxLayout(control_box)
        self.custom_file_label = QLabel("当前图片：未导入")
        self.custom_bg_status_label = QLabel("抠图状态：未处理")
        control_layout.addWidget(self.custom_file_label)
        control_layout.addWidget(self.custom_bg_status_label)

        import_button = QPushButton("导入图片")
        import_button.clicked.connect(self._import_custom_image)
        remove_bg_button = QPushButton("自动抠图")
        remove_bg_button.clicked.connect(self._remove_custom_background)
        generate_button = QPushButton("生成并应用")
        generate_button.clicked.connect(self._generate_custom_cursor)
        control_layout.addWidget(import_button)
        control_layout.addWidget(remove_bg_button)
        control_layout.addWidget(generate_button)

        scale_box = QGroupBox("缩放")
        scale_layout = QHBoxLayout(scale_box)
        self.scale_slider = WheelSafeSlider(Qt.Orientation.Horizontal)
        self.scale_slider.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.scale_slider.setRange(40, 180)
        self.scale_slider.setValue(100)
        self.scale_slider.valueChanged.connect(self._update_custom_preview)
        self.custom_scale_label = QLabel("100%")
        scale_layout.addWidget(self.scale_slider)
        scale_layout.addWidget(self.custom_scale_label)
        control_layout.addWidget(scale_box)

        hotspot_box = QGroupBox("热点设置 (0-63)")
        hotspot_layout = QHBoxLayout(hotspot_box)
        self.hotspot_x_spin = WheelSafeSpinBox()
        self.hotspot_y_spin = WheelSafeSpinBox()
        self._configure_spinbox(self.hotspot_x_spin, 0, 63, 32, width=88)
        self._configure_spinbox(self.hotspot_y_spin, 0, 63, 32, width=88)
        self.hotspot_x_spin.valueChanged.connect(self._update_custom_preview)
        self.hotspot_y_spin.valueChanged.connect(self._update_custom_preview)
        self._custom_controls = [import_button, remove_bg_button, generate_button, self.scale_slider, self.hotspot_x_spin, self.hotspot_y_spin]
        hotspot_layout.addWidget(QLabel("X"))
        hotspot_layout.addWidget(self.hotspot_x_spin)
        hotspot_layout.addWidget(QLabel("Y"))
        hotspot_layout.addWidget(self.hotspot_y_spin)
        control_layout.addWidget(hotspot_box)

        note = QLabel("流程：导入图片 -> 可选自动抠图 -> 自动裁边 -> 缩放居中 -> 设置热点 -> 生成 .cur 并应用。\n首次自动抠图可能需要下载本地 U2Net 模型；拖动中间分隔条可调整左右比例。")
        note.setWordWrap(True)
        control_layout.addWidget(note)
        control_layout.addStretch(1)
        control_panel_layout.addWidget(control_box)

        preview_panel = QWidget()
        preview_panel_layout = QVBoxLayout(preview_panel)
        preview_box = QGroupBox("预览")
        preview_layout = QVBoxLayout(preview_box)
        self.custom_preview_label = QLabel("导入图片后在这里预览")
        self.custom_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.custom_preview_label.setMinimumSize(240, 240)
        preview_layout.addWidget(self.custom_preview_label)
        preview_panel_layout.addWidget(preview_box)

        splitter.addWidget(control_panel)
        splitter.addWidget(preview_panel)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 6)
        splitter.setSizes([420, 700])
        layout.addWidget(splitter)
        return page
    def _build_settings_page(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)

        general_box = QGroupBox("基础设置")
        general_layout = QVBoxLayout(general_box)
        self.startup_checkbox = QCheckBox("开机启动")
        self.startup_checkbox.setChecked(self.context.config.startup.launch_at_startup)
        general_layout.addWidget(self.startup_checkbox)

        appearance_box = QGroupBox("软件主题（浅色 / 深色）")
        appearance_box_layout = QVBoxLayout(appearance_box)
        appearance_box_layout.addWidget(QLabel("这里和首页都可以切换，按钮会直接反映当前模式。"))
        appearance_box_layout.addLayout(self._build_theme_mode_switcher(home=False))
        general_layout.addWidget(appearance_box)

        self.multi_monitor_checkbox = QCheckBox("多屏增强")
        self.multi_monitor_checkbox.setChecked(self.context.config.highlight.multi_monitor)
        general_layout.addWidget(self.multi_monitor_checkbox)
        multi_monitor_hint = QLabel("开启后会尽量在当前鼠标所在屏幕显示提示层；关闭后始终回退到主屏，适合多屏布局固定的人。")
        multi_monitor_hint.setWordWrap(True)
        general_layout.addWidget(multi_monitor_hint)

        hotkey_box = QGroupBox("全局快捷键")
        hotkey_layout = QVBoxLayout(hotkey_box)
        hotkey_layout.addWidget(QLabel("点击录制框后直接按键，不需要手动输入文本。"))
        hotkey_row = QHBoxLayout()
        self.hotkey_edit = QKeySequenceEdit()
        self._configure_hotkey_editor(self.hotkey_edit)
        record_button = QPushButton("录制")
        record_button.clicked.connect(lambda: self._focus_hotkey_editor(self.hotkey_edit))
        hotkey_row.addWidget(self.hotkey_edit, 1)
        hotkey_row.addWidget(record_button)
        hotkey_layout.addLayout(hotkey_row)
        self.settings_hotkey_value_label = QLabel()
        hotkey_layout.addWidget(self.settings_hotkey_value_label)
        preset_row = QHBoxLayout()
        for preset in ("F8", "Shift+F8", "Ctrl+M"):
            preset_button = QPushButton(preset)
            preset_button.clicked.connect(lambda _checked=False, value=preset: self._set_hotkey_widgets(value))
            preset_row.addWidget(preset_button)
        preset_row.addStretch(1)
        hotkey_layout.addLayout(preset_row)
        self.settings_hotkey_hint_label = QLabel()
        self.settings_hotkey_hint_label.setWordWrap(True)
        hotkey_layout.addWidget(self.settings_hotkey_hint_label)
        general_layout.addWidget(hotkey_box)

        duration_row = QHBoxLayout()
        duration_row.addWidget(QLabel("找回鼠标持续时间 (300-5000 ms)"))
        self.duration_spin = WheelSafeSpinBox()
        self._configure_spinbox(self.duration_spin, 300, 5000, self.context.config.highlight.duration_ms)
        duration_row.addWidget(self.duration_spin)
        general_layout.addLayout(duration_row)

        ring_row = QHBoxLayout()
        ring_row.addWidget(QLabel("找回鼠标提示大小 (80-600 px)"))
        self.ring_size_spin = WheelSafeSpinBox()
        self._configure_spinbox(self.ring_size_spin, 80, 600, self.context.config.highlight.ring_size)
        ring_row.addWidget(self.ring_size_spin)
        general_layout.addLayout(ring_row)
        layout.addWidget(general_box)

        pointer_box = QGroupBox("光标显示与晃动提示")
        pointer_layout = QVBoxLayout(pointer_box)
        pointer_size_row = QHBoxLayout()
        pointer_size_row.addWidget(QLabel("全局光标大小 (10-1000%)"))
        self.pointer_size_spin = WheelSafeSlider(Qt.Orientation.Horizontal)
        self.pointer_size_spin.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.pointer_size_spin.setRange(10, 1000)
        self.pointer_size_spin.setValue(max(10, min(1000, self.context.config.pointer.cursor_size_percent)))
        self.pointer_size_spin.setTickInterval(10)
        self.pointer_size_spin.setPageStep(20)
        self.pointer_size_spin.valueChanged.connect(self._on_pointer_size_changed)
        self.pointer_size_input_spin = WheelSafeSpinBox()
        self._configure_spinbox(self.pointer_size_input_spin, 10, 1000, self.pointer_size_spin.value(), step=10, width=112)
        self.pointer_size_input_spin.setSuffix("%")
        self.pointer_size_input_spin.valueChanged.connect(self._on_pointer_size_input_changed)
        pointer_size_row.addWidget(self.pointer_size_spin, 1)
        pointer_size_row.addWidget(self.pointer_size_input_spin)
        pointer_layout.addLayout(pointer_size_row)
        pointer_note = QLabel("推荐范围 50%-500%。你可以直接输入数字或拖动滑条；超出推荐范围会弹出风险提示。大于 500% 时会启用超大跟随指针层，小于 50% 时点击热点会更难观察。")
        pointer_note.setWordWrap(True)
        pointer_layout.addWidget(pointer_note)

        self.shake_to_find_checkbox = QCheckBox("启用快速晃动后显示鼠标尾迹")
        self.shake_to_find_checkbox.setChecked(self.context.config.pointer.shake_to_find_enabled)
        pointer_layout.addWidget(self.shake_to_find_checkbox)

        shake_row = QHBoxLayout()
        shake_row.addWidget(QLabel("晃动触发阈值 (80-1600，越小越容易触发)"))
        self.shake_distance_spin = WheelSafeSlider(Qt.Orientation.Horizontal)
        self.shake_distance_spin.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.shake_distance_spin.setRange(80, 1600)
        self.shake_distance_spin.setSingleStep(10)
        self.shake_distance_spin.setPageStep(40)
        self.shake_distance_spin.setValue(max(80, min(1600, self.context.config.pointer.shake_distance_threshold)))
        self.shake_distance_spin.valueChanged.connect(self._on_shake_threshold_changed)
        self.shake_distance_input_spin = WheelSafeSpinBox()
        self._configure_spinbox(self.shake_distance_input_spin, 80, 1600, self.shake_distance_spin.value(), step=10, width=112)
        self.shake_distance_input_spin.valueChanged.connect(self._on_shake_threshold_input_changed)
        shake_row.addWidget(self.shake_distance_spin, 1)
        shake_row.addWidget(self.shake_distance_input_spin)
        pointer_layout.addLayout(shake_row)
        trail_style_row = QHBoxLayout()
        trail_style_row.addWidget(QLabel("尾迹样式"))
        self.trail_style_combo = QComboBox()
        for style_id, label in self.TRAIL_STYLE_OPTIONS:
            self.trail_style_combo.addItem(label, style_id)
        self.trail_style_combo.setCurrentIndex(max(0, self.trail_style_combo.findData(self.context.config.pointer.trail_style)))
        trail_style_row.addWidget(self.trail_style_combo)
        pointer_layout.addLayout(trail_style_row)

        trail_color_row = QHBoxLayout()
        trail_color_row.addWidget(QLabel("尾迹颜色"))
        self.trail_color_button = QPushButton()
        self.trail_color_button.clicked.connect(self._pick_trail_color)
        trail_color_row.addWidget(self.trail_color_button)
        trail_color_row.addStretch(1)
        pointer_layout.addLayout(trail_color_row)
        pointer_layout.addWidget(QLabel("如果你经常找不到鼠标，建议先把阈值调到 220-420 再试；持续无规则晃动时，尾迹会实时刷新。"))
        layout.addWidget(pointer_box)

        ripple_box = QGroupBox("点击波纹")
        ripple_layout = QVBoxLayout(ripple_box)
        self.click_ripple_checkbox = QCheckBox("启用点击波纹")
        self.click_ripple_checkbox.setChecked(self.context.config.click_ripple.enabled)
        ripple_layout.addWidget(self.click_ripple_checkbox)

        ripple_duration_row = QHBoxLayout()
        ripple_duration_row.addWidget(QLabel("波纹持续时间 (200-2000 ms)"))
        self.ripple_duration_spin = WheelSafeSpinBox()
        self._configure_spinbox(self.ripple_duration_spin, 200, 2000, self.context.config.click_ripple.duration_ms)
        ripple_duration_row.addWidget(self.ripple_duration_spin)
        ripple_layout.addLayout(ripple_duration_row)

        ripple_size_row = QHBoxLayout()
        ripple_size_row.addWidget(QLabel("波纹大小 (40-260 px)"))
        self.ripple_size_spin = WheelSafeSpinBox()
        self._configure_spinbox(self.ripple_size_spin, 40, 260, self.context.config.click_ripple.size)
        ripple_size_row.addWidget(self.ripple_size_spin)
        ripple_layout.addLayout(ripple_size_row)
        layout.addWidget(ripple_box)

        dynamic_box = QGroupBox("动态光标")
        dynamic_layout = QVBoxLayout(dynamic_box)
        self.dynamic_cursor_checkbox = QCheckBox("启用动态光标")
        self.dynamic_cursor_checkbox.setChecked(self.context.config.dynamic_cursor.enabled)
        dynamic_layout.addWidget(self.dynamic_cursor_checkbox)

        dynamic_interval_row = QHBoxLayout()
        dynamic_interval_row.addWidget(QLabel("帧间隔 (90-1000 ms)"))
        self.dynamic_interval_spin = WheelSafeSpinBox()
        self._configure_spinbox(self.dynamic_interval_spin, 90, 1000, self.context.config.dynamic_cursor.frame_interval_ms)
        dynamic_interval_row.addWidget(self.dynamic_interval_spin)
        dynamic_layout.addLayout(dynamic_interval_row)
        dynamic_layout.addWidget(QLabel("当前动态光标对内置主题生效，自定义光标保持静态。"))
        layout.addWidget(dynamic_box)

        app_switch_box = QGroupBox("按程序切换主题")
        app_switch_layout = QVBoxLayout(app_switch_box)
        self.app_switch_checkbox = QCheckBox("启用按程序切换主题")
        self.app_switch_checkbox.setChecked(self.context.config.app_switch.enabled)
        app_switch_layout.addWidget(self.app_switch_checkbox)
        self.app_rules_edit = QTextEdit()
        self.app_rules_edit.setPlaceholderText("例如：\npowerpnt.exe = highlight_arrow\ncode.exe = crosshair")
        self.app_rules_edit.setPlainText(serialize_app_theme_rules(self.context.config.app_switch.rules))
        app_switch_layout.addWidget(self.app_rules_edit)
        app_switch_layout.addWidget(QLabel("每行一条规则，格式：进程名 = 主题ID。注释行可用 # 开头。"))
        layout.addWidget(app_switch_box)

        game_mode_box = QGroupBox("游戏模式")
        game_mode_layout = QVBoxLayout(game_mode_box)
        self.game_mode_checkbox = QCheckBox("全屏应用时自动关闭增强效果")
        self.game_mode_checkbox.setChecked(self.context.config.game_mode.auto_disable_enhancements)
        game_mode_layout.addWidget(self.game_mode_checkbox)
        game_mode_layout.addWidget(QLabel("检测到全屏前台程序时，会暂停找回鼠标、晃动尾迹、点击波纹、动态光标和按程序切换。"))
        layout.addWidget(game_mode_box)

        save_button = QPushButton("保存设置")
        save_button.clicked.connect(self._save_settings)
        layout.addWidget(save_button)
        layout.addWidget(QLabel("保存后会立即更新快捷键、软件主题、光标大小、晃动尾迹和前台应用监控。"))
        layout.addStretch(1)
        return self._wrap_scroll_page(content)

    def _build_about_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        summary = QTextEdit()
        summary.setReadOnly(True)
        summary.setPlainText(
            "\n".join(
                [
                    f"版本：{APP_VERSION}",
                    "技术栈：Python 3.11+ / PySide6 / pywin32 / Pillow / onnxruntime / JSON / PyInstaller",
                    "已实现：主窗口、托盘常驻、热键录制、内置主题切换、主题分部件配色、自定义图片导入、自动抠图、热点设置、.cur 生成与应用、点击波纹、晃动尾迹提示、按程序切换主题、动态光标、全屏自动暂停增强、配置保存、日志。",
                    "第三方组件：本软件使用 PySide6 / Qt for Python 构建桌面界面。PySide6 Community Edition 按 LGPLv3 路径使用。第三方组件许可证见项目 THIRD_PARTY_NOTICES.md 或发布包 licenses 目录。",
                    "说明：部分游戏或自行接管光标的程序仍可能覆盖系统光标应用结果。",
                ]
            )
        )
        layout.addWidget(summary)

        action_box = QGroupBox("维护")
        action_layout = QVBoxLayout(action_box)
        action_layout.addWidget(QLabel("安装版可直接从这里调起卸载程序；便携版和源码运行不会显示可卸载状态。"))
        self.uninstall_button = QPushButton("卸载软件")
        self.uninstall_button.clicked.connect(self._request_uninstall)
        self.uninstall_button.setEnabled(self.context.uninstall_manager.is_available())
        action_layout.addWidget(self.uninstall_button)
        layout.addWidget(action_box)
        layout.addStretch(1)
        return page

    def _configure_hotkey_editor(self, editor: QKeySequenceEdit) -> None:
        if hasattr(editor, "setMaximumSequenceLength"):
            editor.setMaximumSequenceLength(1)
        editor.setMinimumWidth(180)
        editor.keySequenceChanged.connect(self._on_hotkey_sequence_changed)

    def _configure_spinbox(self, spinbox: QSpinBox, minimum: int, maximum: int, value: int, *, step: int = 1, width: int = 96) -> None:
        spinbox.setRange(minimum, maximum)
        spinbox.setSingleStep(step)
        spinbox.setValue(value)
        spinbox.setMinimumWidth(width)
        spinbox.setKeyboardTracking(False)
        spinbox.setAccelerated(True)
        spinbox.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        spinbox.setAlignment(Qt.AlignmentFlag.AlignRight)
        spinbox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.PlusMinus)
        spinbox.setCorrectionMode(QAbstractSpinBox.CorrectionMode.CorrectToNearestValue)
        if spinbox.lineEdit() is not None:
            spinbox.lineEdit().setAlignment(Qt.AlignmentFlag.AlignRight)

    def _wrap_scroll_page(self, content: QWidget) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        return scroll

    def _on_pointer_size_changed(self, value: int) -> None:
        if self.pointer_size_input_spin is not None and self.pointer_size_input_spin.value() != value:
            blocker = QSignalBlocker(self.pointer_size_input_spin)
            self.pointer_size_input_spin.setValue(value)
            del blocker
        if hasattr(self, "pointer_size_value_label") and self.pointer_size_value_label is not None:
            self.pointer_size_value_label.setText(f"{value}%")
        self.context.config.pointer.cursor_size_percent = value
        self._warn_pointer_size_risk_if_needed(value)
        self._refresh_theme_preview()

    def _on_pointer_size_input_changed(self, value: int) -> None:
        if self.pointer_size_spin is not None and self.pointer_size_spin.value() != value:
            blocker = QSignalBlocker(self.pointer_size_spin)
            self.pointer_size_spin.setValue(value)
            del blocker
        self._on_pointer_size_changed(value)

    def _on_shake_threshold_changed(self, value: int) -> None:
        if self.shake_distance_input_spin is not None and self.shake_distance_input_spin.value() != value:
            blocker = QSignalBlocker(self.shake_distance_input_spin)
            self.shake_distance_input_spin.setValue(value)
            del blocker
        if hasattr(self, "shake_distance_value_label") and self.shake_distance_value_label is not None:
            self.shake_distance_value_label.setText(str(value))

    def _on_shake_threshold_input_changed(self, value: int) -> None:
        if self.shake_distance_spin is not None and self.shake_distance_spin.value() != value:
            blocker = QSignalBlocker(self.shake_distance_spin)
            self.shake_distance_spin.setValue(value)
            del blocker
        self._on_shake_threshold_changed(value)
    def _focus_hotkey_editor(self, editor: QKeySequenceEdit | None) -> None:
        if editor is None:
            return
        editor.setFocus(Qt.FocusReason.OtherFocusReason)

    def _on_hotkey_sequence_changed(self, sequence: QKeySequence) -> None:
        hotkey_value = self._normalize_hotkey_text(sequence.toString(QKeySequence.SequenceFormat.PortableText))
        self._set_hotkey_widgets(hotkey_value, sender=self.sender())

    def _set_hotkey_widgets(self, hotkey_value: str, sender=None) -> None:
        normalized = self._normalize_hotkey_text(hotkey_value)
        for editor in (self.quick_hotkey_edit, self.hotkey_edit):
            if editor is None or editor is sender:
                continue
            blocker = QSignalBlocker(editor)
            editor.setKeySequence(QKeySequence(normalized))
            del blocker
        self._update_hotkey_hint_labels(normalized)

    def _update_hotkey_hint_labels(self, hotkey_value: str) -> None:
        hint = describe_hotkey_sequence(hotkey_value)
        if self.home_hotkey_hint_label is not None:
            self.home_hotkey_hint_label.setText(f"热键建议：{hint}")
        if self.settings_hotkey_hint_label is not None:
            self.settings_hotkey_hint_label.setText(f"热键建议：{hint}")
        if self.settings_hotkey_value_label is not None:
            self.settings_hotkey_value_label.setText(f"当前显示：{hotkey_value or '未设置'}")

    def _build_theme_mode_switcher(self, *, home: bool) -> QHBoxLayout:
        row = QHBoxLayout()
        dark_button = QPushButton("深色模式")
        light_button = QPushButton("浅色模式")
        for button in (dark_button, light_button):
            button.setCheckable(True)
            button.setProperty("segmented", True)
            row.addWidget(button)
        row.addStretch(1)
        if home:
            self.home_dark_theme_button = dark_button
            self.home_light_theme_button = light_button
        else:
            self.settings_dark_theme_button = dark_button
            self.settings_light_theme_button = light_button
        dark_button.clicked.connect(lambda checked=False: self._apply_theme_mode("dark"))
        light_button.clicked.connect(lambda checked=False: self._apply_theme_mode("light"))
        self._sync_theme_mode_buttons()
        return row

    def _selected_theme_mode(self) -> str:
        dark_selected = self.home_dark_theme_button is not None and self.home_dark_theme_button.isChecked()
        if dark_selected:
            return "dark"
        light_selected = self.home_light_theme_button is not None and self.home_light_theme_button.isChecked()
        if light_selected:
            return "light"
        return self.context.config.appearance.theme_mode

    def _sync_theme_mode_buttons(self) -> None:
        mode = self.context.config.appearance.theme_mode
        pairs = (
            (self.home_dark_theme_button, self.home_light_theme_button),
            (self.settings_dark_theme_button, self.settings_light_theme_button),
        )
        for dark_button, light_button in pairs:
            if dark_button is None or light_button is None:
                continue
            dark_button.setChecked(mode == "dark")
            light_button.setChecked(mode == "light")

    def _apply_theme_mode(self, mode: str) -> None:
        if mode not in {"dark", "light"}:
            return
        self.context.config.appearance.theme_mode = mode
        self._sync_theme_mode_buttons()
        app = QApplication.instance()
        if app is not None:
            apply_app_theme(app, mode)
        self.context.config_manager.save(self.context.config)
        if self.statusBar() is not None:
            self.statusBar().showMessage(f"已切换到{'深色' if mode == 'dark' else '浅色'}模式。", 2500)

    def _selected_hotkey_value(self) -> str:
        if self.hotkey_edit is None:
            return self.context.config.highlight.hotkey
        return self._normalize_hotkey_text(self.hotkey_edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText))

    def _normalize_hotkey_text(self, value: str) -> str:
        return value.split(",", 1)[0].strip()

    def _pointer_size_risk_zone(self, value: int) -> str:
        if value < 50:
            return "low"
        if value > 500:
            return "high"
        return "safe"

    def _warn_pointer_size_risk_if_needed(self, value: int) -> None:
        zone = self._pointer_size_risk_zone(value)
        if self._pointer_size_warning_zone is None:
            self._pointer_size_warning_zone = zone
            return
        if zone == self._pointer_size_warning_zone or zone == "safe":
            self._pointer_size_warning_zone = zone
            return
        self._pointer_size_warning_zone = zone
        if zone == "high":
            self._show_information("当前光标大小已超过 500%。\n这会启用超大跟随指针层，适合演示或极端放大场景，但日常点击可能会遮挡内容。")
        elif zone == "low":
            self._show_information("当前光标大小已低于 50%。\n这更适合高分辨率精细操作，但点击热点会更难看清。")

    def _show_information(self, text: str) -> None:
        show_information(self, self.context.config.appearance.theme_mode, APP_NAME, text)

    def _show_warning(self, text: str) -> None:
        show_warning(self, self.context.config.appearance.theme_mode, APP_NAME, text)

    def _confirm(self, text: str) -> bool:
        return show_question(self, self.context.config.appearance.theme_mode, APP_NAME, text)

    def _open_color_dialog(self, current_value: str, title: str) -> QColor:
        return pick_color(self, self.context.config.appearance.theme_mode, current_value, title)

    def _refresh_theme_list_selection(self) -> None:
        if self.theme_list is None or self.theme_list.count() == 0:
            return
        target_id = self.context.config.app_state.current_theme.theme_id
        if self.context.config.app_state.current_theme.source != "builtin":
            target_id = BUILTIN_THEMES[0].theme_id
        for index in range(self.theme_list.count()):
            item = self.theme_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == target_id:
                self.theme_list.setCurrentRow(index)
                return
        self.theme_list.setCurrentRow(0)

    def _cycle_theme_selection(self, step: int) -> None:
        if self.theme_list is None or self.theme_list.count() == 0:
            return
        current_row = self.theme_list.currentRow()
        if current_row < 0:
            current_row = 0
        self.theme_list.setCurrentRow((current_row + step) % self.theme_list.count())

    def _selected_theme_id(self) -> str | None:
        if self.theme_list is None or self.theme_list.currentItem() is None:
            return None
        return self.theme_list.currentItem().data(Qt.ItemDataRole.UserRole)

    def _on_theme_selection_changed(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        del previous
        if current is not None:
            self._refresh_theme_preview()

    def _refresh_theme_preview(self) -> None:
        theme_id = self._selected_theme_id()
        if theme_id is None or self.theme_preview_label is None or self.theme_name_label is None or self.theme_description_label is None:
            return
        asset = self.theme_assets.get(theme_id)
        if asset is None:
            return
        preview_image = self.context.cursor_manager.get_preview_image(
            theme_id,
            palette_override=self._selected_theme_palette_override(),
            scale_percent=self.context.config.pointer.cursor_size_percent,
        )
        if preview_image is None:
            self.theme_preview_label.setText("预览生成失败")
        else:
            pixmap = self._pil_to_pixmap(preview_image)
            self.theme_preview_label.setPixmap(pixmap.scaled(240, 240, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.theme_name_label.setText(asset.theme.name)
        self.theme_description_label.setText(asset.theme.description)
        self._refresh_palette_buttons(theme_id)
        if self.quick_theme_label is not None:
            self.quick_theme_label.setText(f"快速主题切换：{asset.theme.name}")

    def _selected_theme_palette_override(self) -> dict[str, str] | None:
        theme_id = self._selected_theme_id()
        if theme_id is None:
            return None
        override = self.context.config.app_state.builtin_theme_palettes.get(theme_id, {})
        return dict(override) if override else None

    def _effective_palette(self, theme_id: str) -> dict[str, str]:
        theme_definition = get_builtin_theme(theme_id)
        if theme_definition is None:
            return {}
        merged = theme_definition.palette.to_dict()
        merged.update(self.context.config.app_state.builtin_theme_palettes.get(theme_id, {}))
        return merged

    def _refresh_palette_buttons(self, theme_id: str) -> None:
        palette = self._effective_palette(theme_id)
        for part, button in self.theme_color_buttons.items():
            color_value = palette.get(part, "#FFFFFF")
            button.setText(color_value.upper())
            button.setStyleSheet(
                f"background-color: {color_value}; color: {self._contrast_text_color(color_value)};"
                "border: 1px solid #CBD5E1; padding: 6px 10px;"
            )

    def _pick_theme_color(self, part: str) -> None:
        theme_id = self._selected_theme_id()
        if theme_id is None:
            return
        current_value = self._effective_palette(theme_id).get(part, "#FFFFFF")
        selected = self._open_color_dialog(current_value, f"选择{self.PALETTE_PART_LABELS[part]}")
        if not selected.isValid():
            return
        override = dict(self.context.config.app_state.builtin_theme_palettes.get(theme_id, {}))
        override[part] = selected.name().upper()
        self.context.config.app_state.builtin_theme_palettes[theme_id] = override
        self.context.config_manager.save(self.context.config)
        self._refresh_theme_preview()
        if self.context.config.app_state.current_theme.theme_id == theme_id and self.context.config.app_state.current_theme.source == "builtin":
            self.context.enhancement_manager.notify_base_theme_changed()
            self._refresh_state_labels()
        self.statusBar().showMessage(f"已更新 {self.PALETTE_PART_LABELS[part]}。", 2500)

    def _reset_selected_theme_palette(self) -> None:
        theme_id = self._selected_theme_id()
        if theme_id is None:
            return
        self.context.config.app_state.builtin_theme_palettes.pop(theme_id, None)
        self.context.config_manager.save(self.context.config)
        self._refresh_theme_preview()
        if self.context.config.app_state.current_theme.theme_id == theme_id and self.context.config.app_state.current_theme.source == "builtin":
            self.context.enhancement_manager.notify_base_theme_changed()
            self._refresh_state_labels()
        self.statusBar().showMessage("已恢复当前主题默认配色。", 2500)

    def _pick_trail_color(self) -> None:
        current_value = self.context.config.pointer.trail_color
        selected = self._open_color_dialog(current_value, "选择尾迹颜色")
        if not selected.isValid():
            return
        self.context.config.pointer.trail_color = selected.name().upper()
        self.context.config_manager.save(self.context.config)
        self._refresh_trail_color_button()
        self.statusBar().showMessage("尾迹颜色已更新。", 2500)

    def _refresh_trail_color_button(self) -> None:
        if self.trail_color_button is None:
            return
        color_value = self.context.config.pointer.trail_color
        self.trail_color_button.setText(color_value.upper())
        self.trail_color_button.setStyleSheet(
            f"background-color: {color_value}; color: {self._contrast_text_color(color_value)};"
            "border: 1px solid #CBD5E1; padding: 6px 10px;"
        )

    def _apply_selected_theme(self) -> None:
        theme_id = self._selected_theme_id()
        if theme_id is None:
            self._show_information("请先选择一个内置主题。")
            return
        asset = self.theme_assets.get(theme_id)
        if asset is None:
            self._show_warning("找不到所选主题资源。")
            return
        palette_override = self._selected_theme_palette_override()
        size_percent = self.context.config.pointer.cursor_size_percent
        if not self.context.cursor_manager.apply_builtin_theme(theme_id, size_percent=size_percent, palette_override=palette_override):
            self._show_warning("应用内置主题失败。某些程序可能会覆盖系统光标。")
            return
        cursor_path = self.context.cursor_manager.get_builtin_cursor_path(theme_id, size_percent=size_percent, palette_override=palette_override)
        self.context.config.app_state.current_theme = CursorTheme(
            theme_id=asset.theme.theme_id,
            theme_name=asset.theme.name,
            source="builtin",
            cursor_path=str(cursor_path) if cursor_path is not None else str(asset.cursor_path),
            hotspot_x=asset.theme.hotspot_x,
            hotspot_y=asset.theme.hotspot_y,
        )
        self.context.config_manager.save(self.context.config)
        self.context.enhancement_manager.notify_base_theme_changed()
        self._refresh_state_labels()
        self.statusBar().showMessage(f"已应用主题：{asset.theme.name}", 3000)

    def _apply_quick_hotkey(self) -> None:
        hotkey_value = self._selected_hotkey_value()
        if not hotkey_value:
            self._show_warning("请先录制一个快捷键。")
            return
        try:
            parse_hotkey_sequence(hotkey_value)
        except ValueError as exc:
            self._show_warning(f"快捷键格式无效：{exc}")
            return
        if self.tray_manager is not None and not self.tray_manager.update_hotkey(hotkey_value):
            self._show_warning("全局快捷键更新失败，请尝试改成 F8、Shift+F8 这类组合。")
            return
        self.context.config.highlight.hotkey = hotkey_value
        self.context.config_manager.save(self.context.config)
        self._refresh_state_labels()
        self.statusBar().showMessage(f"快捷键已更新为 {hotkey_value}", 3000)

    def _restore_system_default(self) -> None:
        if not self.context.cursor_manager.restore_system_default():
            self._show_warning("恢复系统默认光标失败。")
            return
        self.context.config.app_state.current_theme = CursorTheme()
        self.context.config_manager.save(self.context.config)
        self.context.enhancement_manager.notify_base_theme_changed()
        self._refresh_state_labels()
        self.statusBar().showMessage("已恢复系统默认光标。", 3000)
    def _import_custom_image(self) -> None:
        if self._background_task is not None:
            return
        file_path, _ = QFileDialog.getOpenFileName(self, "选择自定义图片", "", "Images (*.png *.jpg *.jpeg *.webp)")
        if not file_path:
            return
        try:
            self.current_custom_project = self.context.image_pipeline.import_image(file_path)
            if self.hotspot_x_spin is not None:
                self.hotspot_x_spin.setValue(32)
            if self.hotspot_y_spin is not None:
                self.hotspot_y_spin.setValue(32)
            if self.scale_slider is not None:
                self.scale_slider.setValue(100)
            self._refresh_custom_labels()
            self._update_custom_preview()
            self.statusBar().showMessage("已导入自定义图片。", 3000)
        except Exception as exc:
            self._show_warning(f"导入图片失败：{exc}")

    def _remove_custom_background(self) -> None:
        if self._background_task is not None:
            return
        if self.current_custom_project is None:
            self._show_information("请先导入一张图片。")
            return
        self._background_task = BackgroundRemovalTask(self.context.image_pipeline, self.current_custom_project, self)
        self._background_task.finished.connect(self._finish_background_removal)
        for control in self._custom_controls:
            control.setEnabled(False)
        self.custom_bg_status_label.setText("抠图状态：处理中")
        self.statusBar().showMessage("正在进行自动抠图，首次可能需要下载模型...")
        self._background_task.start()

    def _finish_background_removal(self) -> None:
        task = self._background_task
        if task is None:
            return
        self._background_task = None
        for control in self._custom_controls:
            control.setEnabled(True)
        task.deleteLater()
        if not self._exit_after_background:
            self._refresh_custom_labels()
            if task.error is None:
                self._update_custom_preview()
                self.statusBar().showMessage("自动抠图完成。", 3000)
            else:
                self.statusBar().showMessage("自动抠图失败，可以重试。", 5000)
                self._show_warning(f"自动抠图失败：{task.error}")
        elif self.tray_manager is not None:
            self.tray_manager.quit_application()
        else:
            self.prepare_for_exit()

    def _generate_custom_cursor(self) -> None:
        if self._background_task is not None:
            return
        if self.current_custom_project is None:
            self._show_information("请先导入一张图片。")
            return
        try:
            cursor_path = self.context.image_pipeline.generate_cursor(
                self.current_custom_project,
                scale_percent=self.scale_slider.value() if self.scale_slider is not None else 100,
                hotspot_x=self.hotspot_x_spin.value() if self.hotspot_x_spin is not None else 32,
                hotspot_y=self.hotspot_y_spin.value() if self.hotspot_y_spin is not None else 32,
            )
            if not self.context.cursor_manager.apply_cursor_file(cursor_path):
                raise RuntimeError("Windows 光标应用失败")
            recent = [str(cursor_path)]
            recent.extend(path for path in self.context.config.app_state.recent_custom_cursors if path != str(cursor_path))
            self.context.config.app_state.recent_custom_cursors = recent[:10]
            self.context.config.app_state.current_theme = CursorTheme(
                theme_id=self.current_custom_project.project_id,
                theme_name=f"自定义 - {self.current_custom_project.display_name}",
                source="custom",
                cursor_path=str(cursor_path),
                hotspot_x=self.hotspot_x_spin.value() if self.hotspot_x_spin is not None else 32,
                hotspot_y=self.hotspot_y_spin.value() if self.hotspot_y_spin is not None else 32,
            )
            self.context.config_manager.save(self.context.config)
            self.context.enhancement_manager.notify_base_theme_changed()
            self._refresh_state_labels()
            self.statusBar().showMessage("已生成并应用自定义光标。", 3000)
        except Exception as exc:
            self._show_warning(f"生成自定义光标失败：{exc}")

    def _update_custom_preview(self) -> None:
        if self.scale_slider is not None and self.custom_scale_label is not None:
            self.custom_scale_label.setText(f"{self.scale_slider.value()}%")
        if self.current_custom_project is None or self.custom_preview_label is None:
            return
        try:
            preview_path = self.context.image_pipeline.generate_preview(
                self.current_custom_project,
                scale_percent=self.scale_slider.value() if self.scale_slider is not None else 100,
                hotspot_x=self.hotspot_x_spin.value() if self.hotspot_x_spin is not None else 32,
                hotspot_y=self.hotspot_y_spin.value() if self.hotspot_y_spin is not None else 32,
            )
            pixmap = QPixmap(str(preview_path))
            self.custom_preview_label.setPixmap(pixmap.scaled(320, 320, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        except Exception as exc:
            self.custom_preview_label.setText(f"预览失败：{exc}")

    def _refresh_state_labels(self) -> None:
        effective_theme = self.context.enhancement_manager.effective_theme
        active_rule = self.context.enhancement_manager.active_rule
        if self.current_theme_label is not None:
            theme_text = f"当前生效主题：{effective_theme.theme_name}"
            if active_rule is not None:
                theme_text += f"（按程序规则：{active_rule.process_name}）"
            self.current_theme_label.setText(theme_text)
        if self.current_hotkey_label is not None:
            hint = describe_hotkey_sequence(self.context.config.highlight.hotkey)
            self.current_hotkey_label.setText(f"找回鼠标快捷键：{self.context.config.highlight.hotkey} | {hint}")
        if self.current_tray_label is not None:
            tray_status = "已启用" if self.tray_manager is not None else "待初始化"
            self.current_tray_label.setText(f"托盘状态：{tray_status}")
        if self.current_process_label is not None:
            process_name = self.context.enhancement_manager.foreground_process_name or "无"
            self.current_process_label.setText(f"前台应用：{process_name}")
        if self.current_runtime_label is not None:
            flags = [f"光标大小 {self.context.config.pointer.cursor_size_percent}%"]
            if self.context.config.pointer.shake_to_find_enabled:
                flags.append(f"晃动尾迹 {self._trail_style_label(self.context.config.pointer.trail_style)}")
            if self.context.config.click_ripple.enabled:
                flags.append("点击波纹")
            if self.context.config.dynamic_cursor.enabled:
                flags.append("动态光标")
            if self.context.config.app_switch.enabled:
                flags.append("按程序切换")
            status = "、".join(flags)
            if self.context.enhancement_manager.game_mode_active:
                status += "，当前因全屏应用已自动暂停增强"
            self.current_runtime_label.setText(f"增强状态：{status}")

    def _refresh_custom_labels(self) -> None:
        if self.custom_file_label is not None:
            if self.current_custom_project is None:
                self.custom_file_label.setText("当前图片：未导入")
            else:
                self.custom_file_label.setText(f"当前图片：{self.current_custom_project.display_name} ({self.current_custom_project.original_path.name})")
        if self.custom_bg_status_label is not None:
            if self.current_custom_project is None:
                self.custom_bg_status_label.setText("抠图状态：未处理")
            elif self.current_custom_project.bg_removed_path is None:
                self.custom_bg_status_label.setText("抠图状态：未运行自动抠图")
            else:
                self.custom_bg_status_label.setText("抠图状态：已生成透明背景结果")

    def _save_settings(self) -> None:
        if self.duration_spin is None or self.ring_size_spin is None or self.pointer_size_spin is None:
            return
        hotkey_value = self._selected_hotkey_value()
        if not hotkey_value:
            self._show_warning("全局快捷键不能为空。")
            return
        try:
            parse_hotkey_sequence(hotkey_value)
        except ValueError as exc:
            self._show_warning(f"全局快捷键无效：{exc}")
            return
        try:
            rules = parse_app_theme_rules(self.app_rules_edit.toPlainText() if self.app_rules_edit is not None else "")
        except ValueError as exc:
            self._show_warning(f"按程序切换规则无效：{exc}")
            return

        if self.tray_manager is not None and not self.tray_manager.update_hotkey(hotkey_value):
            self._show_warning("全局快捷键更新失败，原快捷键及设置已保留。")
            return
        self.context.config.highlight.hotkey = hotkey_value
        self.context.config.highlight.duration_ms = self.duration_spin.value()
        self.context.config.highlight.ring_size = self.ring_size_spin.value()
        self.context.config.highlight.multi_monitor = self.multi_monitor_checkbox.isChecked() if self.multi_monitor_checkbox is not None else True
        self.context.config.pointer.cursor_size_percent = self.pointer_size_input_spin.value() if self.pointer_size_input_spin is not None else self.pointer_size_spin.value()
        self.context.config.appearance.theme_mode = self._selected_theme_mode()
        self.context.config.pointer.shake_to_find_enabled = self.shake_to_find_checkbox.isChecked() if self.shake_to_find_checkbox is not None else True
        self.context.config.pointer.shake_distance_threshold = self.shake_distance_input_spin.value() if self.shake_distance_input_spin is not None else 420
        self.context.config.pointer.trail_style = self.trail_style_combo.currentData() if self.trail_style_combo is not None else "glow"
        self.context.config.pointer.trail_color = self.context.config.pointer.trail_color.upper()
        self.context.config.startup.launch_at_startup = self.startup_checkbox.isChecked() if self.startup_checkbox is not None else False
        self.context.config.click_ripple.enabled = self.click_ripple_checkbox.isChecked() if self.click_ripple_checkbox is not None else False
        self.context.config.click_ripple.duration_ms = self.ripple_duration_spin.value() if self.ripple_duration_spin is not None else 650
        self.context.config.click_ripple.size = self.ripple_size_spin.value() if self.ripple_size_spin is not None else 120
        self.context.config.dynamic_cursor.enabled = self.dynamic_cursor_checkbox.isChecked() if self.dynamic_cursor_checkbox is not None else False
        self.context.config.dynamic_cursor.frame_interval_ms = self.dynamic_interval_spin.value() if self.dynamic_interval_spin is not None else 180
        self.context.config.app_switch.enabled = self.app_switch_checkbox.isChecked() if self.app_switch_checkbox is not None else False
        self.context.config.app_switch.rules = rules
        self.context.config.game_mode.auto_disable_enhancements = self.game_mode_checkbox.isChecked() if self.game_mode_checkbox is not None else True

        startup_ok = self.context.startup_manager.set_enabled(self.context.config.startup.launch_at_startup)
        if not startup_ok:
            self.context.config.startup.launch_at_startup = self.context.startup_manager.is_enabled()
            if self.startup_checkbox is not None:
                self.startup_checkbox.setChecked(self.context.config.startup.launch_at_startup)
            self._show_warning("开机启动写入失败，可能受当前 Windows 权限或注册表环境影响。")

        self.context.config_manager.save(self.context.config)
        app = QApplication.instance()
        if app is not None:
            apply_app_theme(app, self.context.config.appearance.theme_mode)
        self.context.enhancement_manager.refresh_from_config(force_apply=True)
        self._refresh_trail_color_button()
        self._refresh_theme_preview()
        self._refresh_state_labels()
        self.statusBar().showMessage("设置已保存。", 3000)

    def _request_uninstall(self) -> None:
        if self._background_task is not None:
            self._show_warning("请等待自动抠图完成后再卸载。")
            return
        if not self.context.uninstall_manager.is_available():
            self._show_warning("当前运行的是源码版或便携版，未检测到安装版卸载程序。")
            return
        confirmed = self._confirm("将启动 Atlas-X Cursor Studio 的卸载程序。\n卸载过程中可能会要求先关闭当前软件，是否继续？")
        if not confirmed:
            return
        if not self.context.uninstall_manager.launch():
            self._show_warning("卸载程序启动失败，请尝试从开始菜单或控制面板手动卸载。")
            return
        QApplication.instance().quit()

    def _trail_style_label(self, style_id: str) -> str:
        for candidate_id, label in self.TRAIL_STYLE_OPTIONS:
            if candidate_id == style_id:
                return label
        return style_id

    def _pil_to_pixmap(self, image: Image.Image) -> QPixmap:
        rgba = image.convert("RGBA")
        buffer = rgba.tobytes("raw", "RGBA")
        qimage = QImage(buffer, rgba.width, rgba.height, rgba.width * 4, QImage.Format.Format_RGBA8888)
        return QPixmap.fromImage(qimage.copy())

    def _contrast_text_color(self, hex_value: str) -> str:
        color = QColor(hex_value)
        brightness = (color.red() * 299 + color.green() * 587 + color.blue() * 114) / 1000
        return "#0F172A" if brightness > 150 else "#F8FAFC"











