"""
Mathematical calculation support for ALF.

This module evaluates mathematical expressions using SymPy while
restricting expressions to ALF's explicitly supported mathematical
vocabulary.
"""

import re
from tokenize import TokenError

from sympy import (
    Abs,
    E,
    Float,
    Function,
    I,
    Integer,
    Symbol,
    cos,
    diff,
    expand,
    factor,
    gcd,
    integrate,
    limit,
    log,
    pi,
    simplify,
    sin,
    solve,
    sqrt,
    tan,
)
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)


class CalculationError(ValueError):
    """Raised when a mathematical expression cannot be calculated."""


TRANSFORMATIONS = standard_transformations + (
    convert_xor,
    implicit_multiplication_application,
)


PARSER_GLOBALS = {
    "Integer": Integer,
    "Float": Float,
    "Symbol": Symbol,
    "Function": Function,
}


LOCAL_DICT = {
    "E": E,
    "I": I,
    "pi": pi,
    "abs": Abs,
    "cos": cos,
    "diff": diff,
    "expand": expand,
    "factor": factor,
    "gcd": gcd,
    "integrate": integrate,
    "limit": limit,
    "log": log,
    "sin": sin,
    "simplify": simplify,
    "solve": solve,
    "sqrt": sqrt,
    "tan": tan,
}


def _validate_functions(expression):
    """
    Reject function calls outside ALF's allowed mathematical vocabulary.
    """

    for name in re.findall(r"\b[A-Za-z_]\w*\s*\(", expression):
        name = name.rstrip("(").strip()

        if name not in LOCAL_DICT:
            raise CalculationError("unsupported expression")


def _get_local_dict(angle_mode):
    """Return the SymPy vocabulary for the requested angle mode."""

    if angle_mode == "radians":
        return LOCAL_DICT

    if angle_mode == "degrees":
        return {
            **LOCAL_DICT,
            "sin": lambda value: sin(value * pi / 180),
            "cos": lambda value: cos(value * pi / 180),
            "tan": lambda value: tan(value * pi / 180),
        }

    raise CalculationError("invalid angle mode")


def calculate(expression, symbolic=False, places=3, angle_mode="radians"):
    """
    Evaluate a mathematical expression using ALF's allowed SymPy vocabulary.

    Expressions may be evaluated numerically or symbolically. Numeric
    results are rounded to the requested number of decimal places.
    Trigonometric functions use radians by default and may be evaluated
    in degrees by setting ``angle_mode`` to ``"degrees"``.

    Args:
        expression: The mathematical expression to evaluate.
        symbolic: Whether to return the SymPy result instead of a numeric
            value.
        places: Number of decimal places to use when rounding numeric
            results.
        angle_mode: ``"radians"`` or ``"degrees"`` for trigonometric
            functions.

    Returns:
        The evaluated SymPy expression when ``symbolic`` is true;
        otherwise, the numeric result rounded to ``places`` decimal
        places.

    Raises:
        CalculationError: If the expression is unsupported, invalid, or
            cannot produce a numeric result.
    """

    expression = expression.replace("^", "**")
    _validate_functions(expression)

    try:
        result = parse_expr(
            expression,
            global_dict=PARSER_GLOBALS,
            local_dict=_get_local_dict(angle_mode),
            transformations=TRANSFORMATIONS,
        )
    except (SyntaxError, TokenError, TypeError, ValueError) as error:
        raise CalculationError("unsupported expression") from error

    if symbolic:
        return result

    try:
        if not result.is_number:
            raise CalculationError("invalid numeric entry")

        return round(float(result), places)
    except (AttributeError, TypeError, ValueError) as error:
        raise CalculationError("invalid numeric entry") from error
