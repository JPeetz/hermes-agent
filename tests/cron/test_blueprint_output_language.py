"""Output-language anchoring for blueprint-created jobs (#141114 slice 1).

A blueprint's stored prompt is English even when the profile's ``display.language`` is not,
so a zh/de/… user gets English automated briefs on every cron run. ``fill_blueprint`` now
appends one output-language directive derived from ``agent.i18n.get_language()`` (env
``HERMES_LANGUAGE`` > config ``display.language`` > ``en``). English emits nothing, so
default profiles keep byte-identical prompts.
"""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture
def language_home(tmp_path, monkeypatch):
    """Isolated HERMES_HOME for i18n resolution; returns a writer for config.yaml."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    importlib.reload(importlib.import_module("hermes_constants"))
    from hermes_cli import config
    importlib.reload(config)
    _reset_i18n()

    def set_config(language: str) -> None:
        (home / "config.yaml").write_text(
            f"display:\n  language: {language}\n", encoding="utf-8"
        )
        _reset_i18n()

    def clear_config() -> None:
        cfg = home / "config.yaml"
        if cfg.exists():
            cfg.unlink()
        _reset_i18n()

    return set_config, clear_config


def _reset_i18n() -> None:
    from agent import i18n
    i18n.reset_language_cache()


class TestBlueprintOutputLanguage:
    def test_english_default_emits_no_directive(self, language_home):
        # No config, no env var -> en -> prompt byte-identical to the filled template.
        from agent import i18n
        assert i18n.get_language() == "en"
        from cron.blueprint_catalog import fill_blueprint, get_blueprint
        spec = fill_blueprint(get_blueprint("morning-brief"), {"time": "08:30"})
        assert "Output language:" not in spec["prompt"]
        assert spec["prompt"].startswith("Produce a concise morning briefing")

    def test_zh_config_appends_directive(self, language_home):
        set_config, _ = language_home
        set_config("zh")
        from agent import i18n
        assert i18n.get_language() == "zh"
        from cron.blueprint_catalog import fill_blueprint, get_blueprint
        spec = fill_blueprint(get_blueprint("morning-brief"), {"time": "08:30"})
        assert "Output language:" in spec["prompt"]
        assert "简体中文 (zh)" in spec["prompt"]
        assert spec["prompt"].startswith("Produce a concise morning briefing")

    def test_env_override_beats_config(self, language_home, monkeypatch):
        set_config, _ = language_home
        set_config("zh")
        monkeypatch.setenv("HERMES_LANGUAGE", "de")
        _reset_i18n()
        from agent import i18n
        assert i18n.get_language() == "de"
        from cron.blueprint_catalog import fill_blueprint, get_blueprint
        spec = fill_blueprint(get_blueprint("morning-brief"), {"time": "08:30"})
        assert "Deutsch (de)" in spec["prompt"]

    def test_cleared_config_back_to_no_directive(self, language_home):
        set_config, clear_config = language_home
        set_config("zh")
        clear_config()
        from cron.blueprint_catalog import fill_blueprint, get_blueprint
        spec = fill_blueprint(get_blueprint("morning-brief"), {"time": "08:30"})
        assert "Output language:" not in spec["prompt"]
