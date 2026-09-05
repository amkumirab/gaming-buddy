from gaming_buddy.focus_mode import FocusModeState, PinPresentation


def test_focus_mode_restores_panel_and_individual_pin_state() -> None:
    state = FocusModeState()
    original = {
        1: PinPresentation(True, 0.8),
        2: PinPresentation(False, 0.55),
    }

    assert state.enter(panel_visible=True, pins=original)
    state.remember_pin(3, PinPresentation(True, 0.9))
    restored = state.leave()

    assert restored is not None
    assert restored.panel_was_visible
    assert restored.pins == original | {3: PinPresentation(True, 0.9)}
    assert not state.active


def test_focus_mode_lifecycle_is_idempotent() -> None:
    state = FocusModeState()

    assert state.enter(panel_visible=False, pins={})
    assert not state.enter(panel_visible=True, pins={})
    assert state.leave() is not None
    assert state.leave() is None


def test_remember_pin_keeps_earliest_presentation() -> None:
    state = FocusModeState()
    state.enter(panel_visible=False, pins={})

    state.remember_pin(4, PinPresentation(False, 0.6))
    state.remember_pin(4, PinPresentation(True, 1.0))

    restored = state.leave()
    assert restored is not None
    assert restored.pins[4] == PinPresentation(False, 0.6)
