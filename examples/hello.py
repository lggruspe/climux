import sys
from tortoise import Cli, ParamsParser, Renamer, forward, combinators as comb


def hello(*names: str, greeting: str = "Hello") -> str:
    """Say hello."""
    if not names:
        names = ("stranger",)
    return "{}, {}!".format(greeting, ", ".join(names))


parser = ParamsParser({
    "-g": comb.One(str),
    "--greeting": comb.One(str),
    "names": comb.Repeat(comb.One(str), then=tuple),
})

renamer = Renamer()
renamer.add("greeting", "-g", "--greeting", resolve=lambda _, b: b)

cli = Cli(parser, renamer)

if __name__ == "__main__":
    optargs = cli(sys.argv[1:])
    print(forward(optargs, hello))
