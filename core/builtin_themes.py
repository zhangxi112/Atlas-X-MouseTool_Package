"""Built-in cursor theme definitions."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class ThemePalette:
    """A customizable palette used by a built-in cursor theme."""

    primary: str
    secondary: str
    accent: str
    glow: str

    def to_dict(self) -> dict[str, str]:
        """Return a plain dictionary representation for config persistence."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class BuiltinThemeDefinition:
    """Metadata for a built-in cursor theme."""

    theme_id: str
    name: str
    description: str
    hotspot_x: int
    hotspot_y: int
    palette: ThemePalette


BUILTIN_THEMES: tuple[BuiltinThemeDefinition, ...] = (
    BuiltinThemeDefinition("classic_arrow", "普通箭头 Classic Arrow", "接近系统默认的清晰箭头，适合日常办公。", 12, 8, ThemePalette("#FFFFFF", "#0F172A", "#FACC15", "#3B82F6")),
    BuiltinThemeDefinition("round_dot", "圆点 Round Dot", "高对比圆点样式，适合演示与远距离观看。", 32, 32, ThemePalette("#0F172A", "#F1F5F9", "#FACC15", "#38BDF8")),
    BuiltinThemeDefinition("crosshair", "十字 Crosshair", "居中十字线样式，适合精确定位。", 32, 32, ThemePalette("#FFFFFF", "#0F172A", "#FBBF24", "#EF4444")),
    BuiltinThemeDefinition("lightning", "雷电 Lightning", "强调感更强的视觉样式，适合快速识别。", 24, 12, ThemePalette("#FACC15", "#0F172A", "#F59E0B", "#FBBF24")),
    BuiltinThemeDefinition("highlight_arrow", "高亮大箭头 Highlight Arrow", "带高亮边缘的大尺寸箭头，适合多屏或投影场景。", 13, 8, ThemePalette("#FFFFFF", "#166534", "#FACC15", "#22C55E")),
    BuiltinThemeDefinition("neon_arrow", "霓虹箭头 Neon Arrow", "带霓虹描边的箭头，适合深色背景应用。", 12, 8, ThemePalette("#F8FAFC", "#0F172A", "#FB7185", "#EC4899")),
    BuiltinThemeDefinition("comet_arrow", "彗星箭头 Comet Arrow", "箭头后方带拖尾，适合快速找回。", 12, 8, ThemePalette("#FFFFFF", "#0F172A", "#FACC15", "#0EA5E9")),
    BuiltinThemeDefinition("diamond_pointer", "钻石指针 Diamond Pointer", "菱形高亮指针，强调鼠标中心位置。", 32, 18, ThemePalette("#FFFFFF", "#0F172A", "#FACC15", "#3B82F6")),
    BuiltinThemeDefinition("hollow_ring", "空心环 Hollow Ring", "空心圆环样式，适合演示与圈选定位。", 32, 32, ThemePalette("#FFFFFF", "#0F172A", "#111827", "#A855F7")),
    BuiltinThemeDefinition("pinpoint", "定位针 Pinpoint", "类似图钉的定位针样式，适合突出点击点。", 32, 10, ThemePalette("#FFFFFF", "#0F172A", "#FACC15", "#F43F5E")),
    BuiltinThemeDefinition("prism", "棱镜 Prism", "镂空的折面箭头，左上尖端用于点选。", 8, 5, ThemePalette("#E5FFF3", "#173632", "#34D6A4", "#4DEBC2")),
    BuiltinThemeDefinition("orbit", "轨道 Orbit", "开口双环围绕中心定位点，便于对准图纸或幻灯片上的细节。", 32, 32, ThemePalette("#F6F8FF", "#24243A", "#BCB3FF", "#8674FF")),
)


def get_builtin_theme(theme_id: str) -> BuiltinThemeDefinition | None:
    """Return a built-in theme by identifier."""
    for theme in BUILTIN_THEMES:
        if theme.theme_id == theme_id:
            return theme
    return None
