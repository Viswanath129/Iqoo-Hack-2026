# Intentional syntax error for build diagnosis test
def add(a: int, b: int) -> int:
    return (a + b  # Missing closing parenthesis triggers SyntaxError

def multiply(a: int, b: int) -> int:
    return a * b
