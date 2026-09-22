from calc import add, multiply, subtract

def test_add():
    assert add(2, 3) == 5

def test_multiply():
    assert multiply(2, 3) == 6

def test_subtract():
    assert subtract(5, 3) == 2
