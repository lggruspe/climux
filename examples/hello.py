import sys
from genbu import CLInterface, Param, combinators as comb, usage


def hello(*names: str, greeting: str = "Hello") -> str:
    """Say hello."""
    if not names:
        names = ("stranger",)
    return "{}, {}!".format(greeting, ", ".join(names))


cli = CLInterface(
    hello,
    params=[
        Param("greeting", ["-g", "--greeting"], comb.One(str)),
        Param("names", parse=comb.Repeat(comb.One(str), then=tuple)),
        Param(
            "help_",
            ["-?", "-h", "--help"],
            comb.Emit(True),
            aggregator=lambda _: sys.exit(usage(cli))
        ),
    ],
)

if __name__ == "__main__":
    print(cli.run())
