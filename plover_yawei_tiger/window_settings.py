"""Yawei configuration path adapter for the reusable popup settings tool."""

import os
from pathlib import Path

from plover_multi_candidate.window_settings import CandidateWindowSettings


class YaweiCandidateWindowSettings(CandidateWindowSettings):
    """预览并设置亚伟候选窗的字体、颜色和位置，保存后立即应用。"""

    TITLE = "亚伟候选窗设置"
    ROLE = "yawei_candidate_window_settings"
    EXTENSION_NAME = "yawei-rime"

    def _config_paths(self):
        from .extension import _yawei_config_path, _yawei_user_config_dir
        override = os.environ.get("PLOVER_YAWEI_COMMAND_CONFIG")
        target = Path(override) if override else _yawei_user_config_dir() / "yawei_tiger.cfg"
        return target, _yawei_config_path(Path(__file__).resolve().parent)
