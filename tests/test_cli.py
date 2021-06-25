# pylint: disable=disallowed-name,invalid-name,redefined-outer-name
"""Test genbu.cli."""

import sys
import typing as t

from hypothesis import given, strategies as st
import pytest

from genbu import CLInterface, Param, combinators as comb


def make_cli(**kwargs: t.Any) -> CLInterface:
    """CLInterface factory."""
    def callback() -> None:
        """Does nothing."""

    kwargs.setdefault("name", "test-cli")
    kwargs.setdefault("description", "Test CLInterface.")
    kwargs.setdefault("callback", callback)
    return CLInterface(**kwargs)


CLIFactory = t.Callable[[], CLInterface]


@given(
    st.lists(
        st.text().filter(lambda x: not x.strip().startswith("-")),
        min_size=1,
    ),
)
def test_cli_run_without_arguments(argv: t.List[str]) -> None:
    """It should use sys.argv[1:]."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(sys, "argv", argv)
        cli = make_cli(
            params=[Param("arg", parse=comb.Repeat(comb.One(str), then=list))],
            callback=lambda arg: arg,
        )
        assert cli.run() == argv[1:]


def test_cli_run_with_arguments() -> None:
    """Test with positional arguments."""
    cli = make_cli(
        params=[Param("numbers", parse=comb.Repeat(comb.One(float)))],
        callback=lambda numbers: sum(numbers)  # pylint: disable=W0108
    )
    assert cli.run([]) == 0
    assert cli.run(["1.5", "2"]) == 3.5
    assert cli.run(["0.45e-5"]) == 0.45e-5


def test_cli_run_with_short_options() -> None:
    """Test with short options."""
    cli = make_cli(
        params=[
            Param(
                "x",
                ["-a", "-b", "-c"],
                parse=comb.One(int),
                resolve=lambda a, b: a + b,
            ),
        ],
        callback=lambda x: x,
    )
    assert cli.run("-a4 -b 5 -c=6".split()) == 15


def test_cli_run_with_stacked_options() -> None:
    """Test with stacked short options."""
    def callback(a: str = "", b: str = "", c: str = "") -> str:
        return a + b + c

    cli = make_cli(
        params=[
            Param("a", ["-a"], parse=comb.Emit("a")),
            Param("b", ["-b"], parse=comb.Emit("b")),
            Param("c", ["-c"], parse=comb.Emit("c")),
        ],
        callback=callback,
    )
    cases = [
        ("", ""),
        ("-a", "a"),
        ("-ab", "ab"),
        ("-ac", "ac"),
        ("-bc", "bc"),
        ("-abc", "abc"),
        ("-cba", "abc"),
    ]
    for source, expected in cases:
        assert cli.run(source.split()) == expected


def test_cli_run_with_long_options() -> None:
    """Test with long options."""
    cli = make_cli(
        params=[
            Param(
                "x",
                ["--foo", "--bar", "--baz"],
                parse=comb.One(float),
                resolve=lambda a, b: a + b,
            ),
        ],
        callback=lambda x: x,
    )
    assert cli.run("--foo 1 --bar 2 --baz 3".split()) == 6


def test_cli_run_with_long_options_with_equals() -> None:
    """Test with long options with equals (e.g. --foo=bar)."""
    cli = make_cli(
        params=[Param("value", ["--value"], parse=comb.One(int))],
        callback=lambda value: value,
    )

    cases = [("--value=5", 5), ("--valu=6", 6), ("--val=7", 7)]
    for source, expected in cases:
        assert cli.run(source.split()) == expected


@pytest.mark.parametrize("source", ["1", "-i", "-invalid", "--invalid"])
def test_cli_run_with_unknown_options(source: str) -> None:
    """Program should abort if user enters unexpected option."""
    cli = make_cli()
    with pytest.raises(SystemExit):
        cli.run(source.split())
    with pytest.raises(SystemExit):
        cli.run((source + "=foo").split())


def test_cli_run_with_ambiguous_long_options() -> None:
    """Program should abort if long option prefix is ambiguous."""
    cli = make_cli(params=[
        Param("bar", ["--bar"], parse=comb.Emit(True)),
        Param("baz", ["--baz"], parse=comb.Emit(True)),
    ])

    for source in ["--b", "--ba"]:
        with pytest.raises(SystemExit):
            cli.run(source.split())
    cli.run(["--bar"])
    cli.run(["--baz"])


def test_cli_run_with_missing_options() -> None:
    """Program should abort if there are missing arguments."""
    cli = make_cli(
        params=[
            Param("a", parse=comb.One(int)),
            Param("b", ["-b"], parse=comb.One(int)),
            Param("c", ["--c"], parse=comb.One(int)),
        ],
        callback=lambda a, b, c: (a, b, c),
    )
    for source in [
            "-b 1 --c 2",
            "1 --c 2",
            "1 -b 2",
    ]:
        with pytest.raises(SystemExit):
            cli.run(source.split())
    assert cli.run("1 -b 2 --c 3".split()) == (1, 2, 3)


def test_cli_run_with_various_parameter_kinds_in_callback() -> None:
    """CLI arguments should properly be bound to callback params.

    Tested parameter kinds:
    - positional only
    - var positional
    - keyword only
    - var keyword
    """
    def callback(a: int, *b: int, c: int, **d: int) -> t.Any:
        return a, b, c, d

    cli = make_cli(
        params=[
            Param("a", ["-a"], parse=comb.One(int)),
            Param("b", ["-b"], parse=comb.Repeat(comb.One(int))),
            Param("c", ["-c"], parse=comb.One(int)),
            Param("d", ["-d"], parse=comb.Repeat(
                comb.And(comb.One(str), comb.One(int)),
                then=dict,
            )),
        ],
        callback=callback,
    )

    assert cli.run("-a 1 -b 2 -c 3 -d k 4".split()) == (1, (2,), 3, {"k": 4})
    assert cli.run("-a 1 -c 2".split()) == (1, (), 2, {})


def test_cli_run_with_subparsers() -> None:
    """Test with subparsers."""
    bar = CLInterface(
        name="bar",
        description="Bar.",
        callback=lambda: "bar",
    )

    baz = CLInterface(
        name="baz",
        description="Baz.",
        callback=lambda: "baz",
    )

    foo = CLInterface(
        name="foo",
        description="Foo.",
        callback=lambda: "foo",
        subparsers=[bar, baz],
    )

    assert foo.run([]) == "foo"
    assert foo.run(["bar"]) == "bar"
    assert foo.run(["baz"]) == "baz"

    for source in ["ba", "oof", "-h"]:
        with pytest.raises(SystemExit):
            foo.run(source.split())


def test_clinterface_name_and_description_are_optional() -> None:
    """It should infer name and description from callback instead."""
    def hello() -> None:
        """Hello, world!"""

    cli = CLInterface(hello)

    assert cli.name == "hello"
    assert cli.description == "Hello, world!"
