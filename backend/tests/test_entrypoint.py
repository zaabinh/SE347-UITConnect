from unittest.mock import Mock

from app import __main__ as launcher


def test_launcher_uses_validated_host_and_port_without_reload(monkeypatch):
    config = launcher.settings.model_copy(update={"app_host": "127.0.0.1", "port": 8123})
    monkeypatch.setattr(launcher, "settings", config)
    run = Mock()
    monkeypatch.setattr(launcher.uvicorn, "run", run)
    launcher.main()
    run.assert_called_once_with(
        "app.main:app", host="127.0.0.1", port=8123, reload=False, log_level="info"
    )
