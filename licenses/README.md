# Release License Files

The release package should include this directory as `licenses/`.

Included license texts:

- `LGPL-3.0.txt`
- `GPL-3.0.txt`

The GPL and LGPL texts are verbatim copies from the official Qt 6.10.2 source tree:

- https://github.com/qt/qtbase/blob/v6.10.2/LICENSES/LGPL-3.0-only.txt
- https://github.com/qt/qtbase/blob/v6.10.2/LICENSES/GPL-3.0-only.txt

The build also collects license/copying files supplied by the installed PySide6, Shiboken, Pillow, NumPy, ONNX Runtime and pywin32 distributions into package-specific subdirectories. The project MIT license and `THIRD_PARTY_NOTICES.md` are bundled too. In the one-directory executable layout, these resources are under `_internal/`.

Atlas-X Cursor Studio uses PySide6 Community Edition under the LGPLv3 path. The project does not choose the PySide6 GPL path and does not modify PySide6, Qt, or Shiboken source code.
