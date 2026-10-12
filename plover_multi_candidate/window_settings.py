"""Plover Tools dialog for candidate popup appearance and placement."""

from __future__ import annotations

import configparser
import os
from pathlib import Path

from plover.gui_qt.tool import Tool

from . import controller as ui
from .state import CandidateState
from .window_config import load_window_settings, save_window_settings

if ui.QFrame.__module__.startswith("PySide6"):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QFont
    from PySide6.QtWidgets import (
        QColorDialog, QComboBox, QFontComboBox, QFormLayout, QGroupBox,
        QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
        QSpinBox, QVBoxLayout, QWidget,
    )
else:  # pragma: no cover - older Plover Qt runtime
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QColor, QFont
    from PyQt5.QtWidgets import (
        QColorDialog, QComboBox, QFontComboBox, QFormLayout, QGroupBox,
        QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
        QSpinBox, QVBoxLayout, QWidget,
    )


POSITION_LABELS = (
    ("左上", "top_left"), ("上中", "top_center"), ("右上", "top_right"),
    ("左中", "middle_left"), ("右中", "middle_right"),
    ("左下", "bottom_left"), ("下中", "bottom_center"), ("右下", "bottom_right"),
)


class CandidateWindowSettings(Tool):
    """设置候选窗字体、颜色和位置，预览后保存并立即应用。"""

    TITLE = "候选窗设置"
    ROLE = "multi_candidate_window_settings"
    EXTENSION_NAME = "multi-candidate"

    def _config_paths(self):
        from .extension import _config_path, _user_config_dir
        override = os.environ.get("PLOVER_MULTI_CANDIDATE_CONFIG")
        target = Path(override) if override else _user_config_dir() / "multi_candidate.cfg"
        return target, _config_path()

    def __init__(self, engine):
        super().__init__(engine)
        self.setMinimumWidth(580)
        self._path, self._fallback = self._config_paths()
        self._fields = {}
        self._loading = False
        self._load_error = None
        extension = getattr(engine, "_running_extensions", {}).get(self.EXTENSION_NAME)
        try:
            values = load_window_settings(self._path, self._fallback)
        except (OSError, UnicodeError, configparser.Error) as exc:
            self._load_error = str(exc)
            values = ui.normalize_window_config()
        if extension is not None:
            values = dict(extension._window_config)
        self._original = values
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        font = self._fields["font_family"] = QFontComboBox(self)
        font.currentFontChanged.connect(self._update_preview)
        form.addRow("字体", font)
        for key, label, maximum in (
            ("buffer_font_size", "缓冲行字号", 72),
            ("preedit_font_size", "输入编码字号", 72),
            ("candidate_font_size", "候选字号", 72),
            ("width", "候选窗最小宽度", 4096),
            ("max_candidates", "最多显示候选", 99),
            ("margin", "屏幕边距", 256),
        ):
            field = self._fields[key] = QSpinBox(self)
            field.setRange(1, max(maximum, values[key]))
            field.valueChanged.connect(self._update_preview)
            form.addRow(label, field)
        for key, label in (("background", "背景色"), ("foreground", "文字色"), ("accent", "候选高亮色")):
            row = QWidget(self)
            colors = QHBoxLayout(row)
            colors.setContentsMargins(0, 0, 0, 0)
            field = self._fields[key] = QLineEdit(row)
            field.textChanged.connect(self._update_preview)
            choose = QPushButton("选择…", row)
            choose.clicked.connect(lambda checked=False, name=key: self._choose_color(name))
            colors.addWidget(field)
            colors.addWidget(choose)
            form.addRow(label, row)
        mode = self._fields["position_mode"] = QComboBox(self)
        mode.addItem("跟随输入光标", "follow")
        mode.addItem("固定在屏幕位置", "fixed")
        mode.currentIndexChanged.connect(self._update_preview)
        form.addRow("位置方式", mode)
        position = self._fields["fixed_position"] = QComboBox(self)
        for label, value in POSITION_LABELS:
            position.addItem(label, value)
        position.currentIndexChanged.connect(self._update_preview)
        form.addRow("固定位置", position)

        group = QGroupBox("预览", self)
        preview_layout = QVBoxLayout(group)
        self.preview = ui.CandidateWindow(None, values)
        self.preview.setParent(group)
        self.preview.setWindowFlags(Qt.Widget)
        self.preview.set_state(CandidateState(
            buffered="今天练习速录", candidates=["爸爸", "粑粑", "巴巴"], show_preedit=True,
        ))
        preview_layout.addWidget(self.preview)
        layout.addWidget(group)
        self.status = QLabel(self)
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.PlainText)
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.status)
        buttons = QHBoxLayout()
        defaults = QPushButton("恢复默认", self)
        defaults.clicked.connect(lambda: self._populate(ui.normalize_window_config()))
        buttons.addWidget(defaults)
        buttons.addStretch()
        self.apply_button = QPushButton("保存并应用", self)
        self.apply_button.clicked.connect(self._save)
        buttons.addWidget(self.apply_button)
        close = QPushButton("关闭", self)
        close.clicked.connect(self.close)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        self._populate(values)
        self.status.setText(f"设置保存在：{self._path}")
        if self._load_error is not None:
            self.apply_button.setEnabled(False)
            self.status.setText(f"配置读取失败，请先修复配置文件：{self._load_error}")

    def _populate(self, values):
        self._loading = True
        try:
            for key, field in self._fields.items():
                if key == "font_family":
                    field.setCurrentFont(QFont(values[key]))
                elif isinstance(field, QSpinBox):
                    field.setValue(values[key])
                elif isinstance(field, QComboBox):
                    field.setCurrentIndex(field.findData(values[key]))
                else:
                    field.setText(values[key])
        finally:
            self._loading = False
        self._update_preview()

    def _values(self):
        values = dict(self._original)
        for key, field in self._fields.items():
            if key == "font_family":
                values[key] = field.currentFont().family()
            elif isinstance(field, QSpinBox):
                values[key] = field.value()
            elif isinstance(field, QComboBox):
                values[key] = field.currentData()
            else:
                values[key] = field.text().strip()
        return ui.normalize_window_config(values)

    def _update_preview(self, *args):
        if self._loading or not hasattr(self, "preview"):
            return
        values = self._values()
        self._fields["fixed_position"].setEnabled(values["position_mode"] == "fixed")
        if all(QColor(values[key]).isValid() for key in ("background", "foreground", "accent")):
            self.preview.apply_config(values)

    def _choose_color(self, name):
        color = QColorDialog.getColor(QColor(self._fields[name].text()), self, "选择颜色")
        if color.isValid():
            self._fields[name].setText(color.name())

    def _save(self):
        if self._load_error is not None:
            return
        values = self._values()
        if not all(QColor(values[key]).isValid() for key in ("background", "foreground", "accent")):
            QMessageBox.warning(self, self.TITLE, "颜色格式不正确，请选择颜色或填写 #RRGGBB。")
            return
        try:
            values = save_window_settings(self._path, values, self._fallback)
        except (OSError, UnicodeError, configparser.Error) as exc:
            QMessageBox.warning(self, self.TITLE, f"保存失败，当前设置未应用：{exc}")
            return
        self._original = values
        extension = getattr(self._engine, "_running_extensions", {}).get(self.EXTENSION_NAME)
        if extension is not None:
            extension.apply_candidate_window_config(values)
            self.status.setText(f"已保存并应用：{self._path}")
        else:
            self.status.setText(f"已保存，启用候选扩展后生效：{self._path}")
