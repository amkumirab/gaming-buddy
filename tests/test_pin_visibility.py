from PySide6.QtCore import QCoreApplication

from gaming_buddy.pin_visibility import PinVisibilityController


def _application() -> QCoreApplication:
    return QCoreApplication.instance() or QCoreApplication([])


def test_pins_hide_after_delay_and_restore_when_game_returns() -> None:
    _application()
    controller = PinVisibilityController(delay_ms=5000)
    hidden: list[bool] = []
    restored: list[bool] = []
    controller.auto_hide_requested.connect(lambda: hidden.append(True))
    controller.auto_restore_requested.connect(lambda: restored.append(True))

    controller.set_enabled(True)
    assert controller.hide_timer.isActive()
    controller._apply_auto_hide()

    assert hidden == [True]
    assert controller.automatically_hidden

    controller.update_focus(True)

    assert restored == [True]
    assert not controller.automatically_hidden


def test_quick_return_to_game_cancels_pending_hide() -> None:
    _application()
    controller = PinVisibilityController(delay_ms=5000)
    hidden: list[bool] = []
    controller.auto_hide_requested.connect(lambda: hidden.append(True))

    controller.set_enabled(True)
    controller.update_focus(True)
    controller._apply_auto_hide()

    assert not controller.hide_timer.isActive()
    assert hidden == []


def test_manual_hide_is_preserved_across_focus_changes() -> None:
    _application()
    controller = PinVisibilityController(delay_ms=5000)
    restored: list[bool] = []
    controller.auto_restore_requested.connect(lambda: restored.append(True))

    controller.set_enabled(True)
    controller.manual_hide()
    controller.update_focus(True)
    controller.update_focus(False)

    assert controller.manually_hidden
    assert not controller.hide_timer.isActive()
    assert restored == []


def test_manual_show_overrides_current_app_until_focus_changes() -> None:
    _application()
    controller = PinVisibilityController(delay_ms=5000)
    controller.set_enabled(True)
    controller._apply_auto_hide()
    assert controller.automatically_hidden

    controller.manual_show()
    assert not controller.automatically_hidden
    assert not controller.hide_timer.isActive()

    controller.update_focus(False)
    assert controller.hide_timer.isActive()


def test_disabling_feature_restores_only_auto_hidden_pins() -> None:
    _application()
    controller = PinVisibilityController(delay_ms=5000)
    restored: list[bool] = []
    controller.auto_restore_requested.connect(lambda: restored.append(True))
    controller.set_enabled(True)
    controller._apply_auto_hide()

    controller.set_enabled(False)

    assert restored == [True]
    assert not controller.automatically_hidden
