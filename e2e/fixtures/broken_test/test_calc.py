from calc import add, multiply


def test_add():
    # 2 + 3 should be 5, but calc.add returns -1
    assert add(2, 3) == 5, f"Expected 5, got {add(2, 3)}"

def test_multiply():
    assert multiply(2, 3) == 6
