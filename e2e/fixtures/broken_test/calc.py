# Valid syntax, but deliberate semantic bug causing unit test failure
def add(a: int, b: int) -> int:
    return a - b  # Deliberate bug: subtraction instead of addition

def multiply(a: int, b: int) -> int:
    return a * b
