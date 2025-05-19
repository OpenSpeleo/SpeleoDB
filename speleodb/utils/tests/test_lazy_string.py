from speleodb.utils.lazy_string import LazyString


def test_lazy_evaluation():
    called = False

    def lazy_func():
        nonlocal called
        called = True
        return "Lazy evaluated string"

    lazy_str = LazyString(lazy_func)

    # Initially, the function should not have been called
    assert not called

    # Accessing the data should trigger the lazy evaluation
    assert lazy_str.data == "Lazy evaluated string"
    assert called


def test_direct_value_set():
    lazy_str = LazyString(lambda: "Lazy evaluated string")

    # Setting the value directly
    lazy_str.data = "Directly set value"
    assert lazy_str.data == "Directly set value"


def test_lazy_str_with_str():
    assert isinstance(LazyString("not a callable"), str)  # type: ignore[arg-type]


def test_no_re_evaluation():
    called_count = 0

    def lazy_func():
        nonlocal called_count
        called_count += 1
        return "Lazy evaluated string"

    lazy_str = LazyString(lazy_func)

    # Trigger lazy evaluation
    assert lazy_str.data == "Lazy evaluated string"
    assert called_count == 1

    # Accessing the data again should not trigger re-evaluation
    assert lazy_str.data == "Lazy evaluated string"
    assert called_count == 1


def test_inheritance_from_userstring():
    str_val = "Lazy evaluated string"

    def lazy_func():
        return str_val

    lazy_str = LazyString(lazy_func)

    # Ensure LazyString behaves like a string
    assert str(lazy_str) == str_val
    assert len(lazy_str) == len(str_val)
    assert lazy_str.upper() == str_val.upper()
