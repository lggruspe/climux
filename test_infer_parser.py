"""Test infer_parser.py."""

from typing import Annotated, Final, List, Optional, Tuple, Union
from infer_parser import CantInfer, CantParse, infer, parse_bool, parse_none


def test_parse_none():
    """parse_none should parse '' and 'None' to None and nothing else."""
    assert parse_none("") is None
    assert parse_none("None") is None
    assert parse_none("none") is not None


def test_parse_bool():
    """parse_bool should parse only 'true', 'True', '1' to True."""
    truthy = ["true", "True", "1"]
    assert all(map(parse_bool, truthy))

    falsy = ["", "false", "False", "0"]
    assert not any(map(parse_bool, falsy))

    assert isinstance(parse_bool("TRue"), CantParse)
    assert isinstance(parse_bool("false "), CantParse)


def test_infer_none():
    """infer should return parse_none on None."""
    assert infer(None) == parse_none


def test_infer_bool():
    """infer should return parse_bool on bool."""
    assert infer(bool) == parse_bool


def test_infer_type():
    """infer should wrap basic and class types to return CantParse on error."""
    parse_float = infer(float)
    assert parse_float("1.5") == 1.5
    assert parse_float("9.0") == 9.0
    assert isinstance(parse_float("test"), CantParse)

    parse_int = infer(int)
    assert parse_int("-5") == -5
    assert parse_int("9002") == 9002
    assert isinstance(parse_int("0.0"), CantParse)


def test_infer_class_type():
    """infer should wrap custom types."""
    class Ok:
        def __init__(self, arg: str):
            pass

    class Err:
        pass

    ok = infer(Ok)
    err = infer(Err)
    assert isinstance(ok("test"), Ok)
    assert isinstance(err("test"), CantParse)


def test_infer_optional_type():
    """infer should work with optional types."""
    parse = infer(Optional[float])
    assert parse("1.5") == 1.5
    assert parse("") is None
    assert parse("None") is None
    assert parse("5") == 5.0


def test_infer_union_type():
    """infer should work with union types."""
    parse = infer(Union[int, bool])
    assert not parse("")
    assert not parse("false")
    assert not parse("False")
    assert parse("0") == 0
    assert parse("42") == 42
    assert isinstance(parse("e"), CantParse)

    zero = infer(Union[bool, int])("0")
    assert not zero
    assert isinstance(zero, bool)


def test_infer_final_type():
    """infer should work with final types."""
    parse = infer(Final[int])
    assert parse("17") == 17


def test_infer_annotated_type():
    """infer should work with annotated types."""
    parse = infer(Annotated[bool, None])
    assert parse("false") is False
    assert parse("True") is True


def test_infer_finite_tuple_type():
    """infer should work with finite tuple types."""
    parse = infer(tuple[int, float])
    result = parse("5 5")
    assert isinstance(result, tuple)
    assert isinstance(result[0], int)
    assert isinstance(result[1], float)
    assert result == (5, 5.0)

    assert isinstance(parse("5"), CantParse)
    assert isinstance(parse("5.0 5"), CantParse)
    assert parse("  0  '1.5'   ") == (0, 1.5)

    assert infer(Tuple[bool, bool, bool])("True true 1") == \
        (True, True, True)


def test_infer_list_type():
    """infer should work with list types."""
    parse = infer(list[float])
    result = parse("0.0 1.1 2.2 '3.3'")

    assert all(isinstance(r, float) for r in result)
    assert result == [0.0, 1.1, 2.2, 3.3]

    assert infer(List[bool])("true True 1") == [True, True, True]
    assert isinstance(infer(List[int])("1 2 3 four"), CantParse)


def test_infer_nested_type():
    """infer should work with nested types."""
    parse = infer(Final[Union[Union[int, bool], Optional[float]]])
    assert parse("19.5") == 19.5
    assert parse("false") is False
    assert parse("None") is None


def test_infer_fail():
    """infer should return CantInfer on failure."""
    assert isinstance(infer(...), CantInfer)
    assert isinstance(infer(tuple[int, ...]), CantInfer)
    assert isinstance(infer(Tuple[int, ...]), CantInfer)
