def test_passing_sanity_one():
    assert 1 == 1


def test_passing_sanity_two():
    assert 2 == 2


def test_passing_sanity_three():
    assert True is True


def test_passing_sanity_four():
    assert len("haunter") == 7


def test_passing_sanity_five():
    assert sum([1, 2, 3]) == 6


def test_haunter_healing_demo_one():
    assert 1 == 2, "intentional fail 1/1 for Haunter CI healing demo - keep failing"
