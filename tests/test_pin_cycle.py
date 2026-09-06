from gaming_buddy.pin_cycle import PinCycleState


def test_forward_cycle_starts_with_first_card_and_wraps() -> None:
    cycle = PinCycleState()

    first = cycle.enter((8, 3, 5), {8: True, 3: False, 5: True})

    assert first is not None
    assert (first.card_id, first.position, first.total) == (8, 1, 3)
    second = cycle.move(1)
    third = cycle.move(1)
    assert second is not None and second.card_id == 3
    assert third is not None and third.card_id == 5
    wrapped = cycle.move(1)
    assert wrapped is not None
    assert (wrapped.card_id, wrapped.position) == (8, 1)


def test_backward_cycle_starts_with_last_card_and_wraps() -> None:
    cycle = PinCycleState()

    current = cycle.enter((10, 20, 30), {}, backwards=True)

    assert current is not None
    assert (current.card_id, current.position) == (30, 3)
    previous = cycle.move(-1)
    wrapped = cycle.move(-2)
    assert previous is not None and previous.card_id == 20
    assert wrapped is not None and wrapped.card_id == 30


def test_leaving_cycle_restores_original_visibility() -> None:
    cycle = PinCycleState()
    visibility = {1: True, 2: False, 9: True}
    cycle.enter((1, 2), visibility)

    restored = cycle.leave()

    assert restored is not None
    assert restored.visibility == visibility
    assert not cycle.active
    assert cycle.current is None
    assert cycle.leave() is None


def test_empty_or_duplicate_card_lists_are_handled_safely() -> None:
    cycle = PinCycleState()

    assert cycle.enter((), {}) is None
    current = cycle.enter((4, 4, 7), {})

    assert current is not None
    assert current.total == 2
    assert cycle.card_ids == (4, 7)
