from py_pkg import greet


def test_greet():
    assert greet("World") == "Hello from Python, World!"
