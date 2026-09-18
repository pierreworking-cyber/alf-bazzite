import pytest
from sympy import Symbol, pi, sin

from alf.calc import CalculationError, calculate


def test_basic_arithmetic():
    assert calculate("12 * 7") == 84.0
    assert calculate("(10 + 5) / 3") == 5.0


def test_power_operator():
    assert calculate("2^4") == 16.0


def test_implicit_multiplication():
    assert calculate("2x", symbolic=True) == 2 * Symbol("x")
    assert calculate("3(x + 1)", symbolic=True) == 3 * (Symbol("x") + 1)


def test_allowed_functions():
    x = Symbol("x")

    assert calculate("diff(x^2, x)", symbolic=True) == 2 * x
    assert calculate("integrate(x^2, x)", symbolic=True) == x**3 / 3
    assert calculate("solve(x^2 - 4, x)", symbolic=True) == [-2, 2]
    assert calculate("sin(pi / 2)") == 1.0
    assert calculate("tan(pi / 4)") == 1.0


def test_advertised_abs_and_gcd_functions():
    assert calculate("abs(-42)") == 42.0
    assert calculate("gcd(84, 18)") == 6.0


def test_advertised_simplify_function():
    x = Symbol("x")

    assert calculate("simplify((x^2 - 1)/(x - 1))", symbolic=True) == x + 1


def test_non_numeric_result_raises_calculation_error():
    with pytest.raises(CalculationError):
        calculate("solve(x^2 - 4, x)")


def test_complex_result_raises_calculation_error():
    with pytest.raises(CalculationError):
        calculate("I")


def test_allowed_constants():
    assert calculate("log(E)") == 1.0
    assert calculate("cos(0)") == 1.0


def test_trigonometric_functions_default_to_radians():
    assert calculate("sin(pi / 2)") == 1.0
    assert calculate("cos(pi)") == -1.0
    assert calculate("tan(pi / 4)") == 1.0


def test_trigonometric_functions_support_degrees():
    assert calculate("sin(90)", angle_mode="degrees") == 1.0
    assert calculate("cos(180)", angle_mode="degrees") == -1.0
    assert calculate("tan(45)", angle_mode="degrees") == 1.0


def test_trigonometric_functions_support_symbolic_degrees():
    x = Symbol("x")

    assert calculate("sin(x)", symbolic=True, angle_mode="degrees") == (
        sin(x * pi / 180)
    )


def test_invalid_angle_mode_is_rejected():
    with pytest.raises(CalculationError):
        calculate("sin(90)", angle_mode="gradians")


def test_unknown_function_is_rejected():
    with pytest.raises(CalculationError):
        calculate("arctan(pi / 4)")


def test_unrelated_unsupported_function_is_still_rejected():
    with pytest.raises(CalculationError):
        calculate("floor(2.7)")

    with pytest.raises(CalculationError):
        calculate("sec(0)")

    with pytest.raises(CalculationError):
        calculate("cosh(0)")


def test_malformed_expression_is_rejected():
    with pytest.raises(CalculationError):
        calculate("pi(cos(45)")


def test_python_import_is_rejected():
    with pytest.raises(CalculationError):
        calculate("__import__('os')")

    with pytest.raises(CalculationError):
        calculate("__import__('subprocess')")
