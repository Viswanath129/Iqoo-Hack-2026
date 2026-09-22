try:
    from calc import add, multiply
except SyntaxError:
    add = None
    multiply = None

def test_add():
    assert add is not None, "Failed to import add due to SyntaxError"
    assert add(2, 3) == 5
