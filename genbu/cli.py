"""CLI parser."""

import collections
import inspect
import sys
import textwrap
import typing as t

from .exceptions import CLError
from .forward import MissingArgument, to_args_kwargs
from .normalize import normalize
from .params import Param, UnknownOption


ExceptionHandler = t.Callable[["CLInterface", CLError], t.NoReturn]


def default_error_handler(cli: "CLInterface", exc: CLError) -> t.NoReturn:
    """Default exception handler."""
    name = " ".join(cli.complete_name())
    sys.exit(f"{name}: {exc}")


class CLInterface:  # pylint: disable=R0902,R0913
    """Shell (argv) parser."""
    def __init__(self,
                 *,
                 name: str,
                 description: str,
                 params: t.Optional[list[Param]] = None,
                 subparsers: t.Optional[t.Sequence["CLInterface"]] = None,
                 callback: t.Callable[..., t.Any],
                 error_handler: ExceptionHandler = default_error_handler):
        assert not any(c.isspace() for c in name)

        self.name = name
        self.description = textwrap.dedent(description.strip())
        self.params = list(params or ())
        self.subparsers = {s.name: s for s in subparsers or []}
        self.callback = callback
        self.error_handler = error_handler
        self.parent = None

        self.options = {}
        self.arguments = {}

        for param in params or ():
            for optarg in param.optargs:
                if optarg.startswith("-"):
                    self.options[optarg] = param
                else:
                    self.arguments[optarg] = param

        for sub in self.subparsers.values():
            sub.parent = self

    def complete_name(self) -> tuple[str, ...]:
        """Return complete command name (includes parents)."""
        if self.parent is None:
            return (self.name,)
        return self.parent.complete_name() + (self.name,)

    def expand(self, prefix: str) -> str:
        """Expand prefix to long option.

        Return prefix if it's a short option and it exists.
        Otherwise, raise UnknownOption.
        Also raise error if the prefix is ambiguous.
        """
        if not prefix.startswith("--"):
            if prefix in self.options:
                return prefix
            raise UnknownOption(prefix)

        candidates = [o for o in self.options if o.startswith(prefix)]
        if len(candidates) != 1:
            raise UnknownOption(prefix)
        return candidates[0]

    def parse_opt(self,
                  prefix: str,
                  args: t.Sequence[str],
                  ) -> tuple[str, t.Any, list[str]]:
        """Parse option.

        Return expanded option name, parsed value and unparsed tokens."""
        assert prefix.startswith("-")
        name = self.expand(prefix)
        param = self.options.get(name)
        if param is None:
            raise UnknownOption(name)
        parse = param.parse

        deque = collections.deque(args)
        value = parse(deque).value
        return (name, value, list(deque))

    def takes_params(self) -> bool:
        """Check if CLInterface can directly take Params."""
        return bool(self.params)

    def has_subcommands(self) -> bool:
        """Check if CLInterface has named subcommands."""
        return bool(self.subparsers)

    def parse(self, argv: t.Sequence[str]) -> "Namespace":
        """Parse commands, options and arguments from argv.

        Parse argv in three passes.
        0. Parse commands.
        1. Parse options.
        2. Parse arguments.

        Note: parsers may throw CantParse.
        Long option expansion may raise UnknownOption.
        """
        route: list["CLInterface"] = []
        deque = collections.deque(argv)
        try:
            while deque:
                prev = len(route)
                for name, sub in self.subparsers.items():
                    if name == deque[0]:
                        route.append(sub)
                        deque.popleft()
                        break
                if prev == len(route):
                    break

            subparser = route[-1] if route else self
            optargs = self.parse_optargs(subparser, deque)
            return Namespace(optargs, route[0] if route else self)
        except CLError as exc:
            subparser = route[-1] if route else self
            subparser.error_handler(subparser, exc)

    def __call__(self, argv: t.Sequence[str]) -> t.Any:
        """Parse argv and run callback."""
        namespace = self.parse(argv)
        return namespace.bind(namespace.cli.callback)

    @staticmethod
    def parse_optargs(subparser: "CLInterface",
                      argv: t.Sequence[str],
                      ) -> dict[str, t.Any]:
        """Parse options and arguments from argv using custom subparser.

        Assume program name and subcommands have been removed.
        """
        normalized = normalize(subparser.params, argv)
        args = normalized.arguments
        opts = normalized.options
        optargs = []

        for opt in opts:
            name, value, unused = subparser.parse_opt(opt[0], opt[1:])
            optargs.append((name, value))
            args.extend(unused)

        deque = collections.deque(args)
        for name, param in subparser.arguments.items():
            optargs.append((name, param.parse(deque).value))

        if deque:
            raise UnknownOption(deque[0])

        renamed = Renamer(subparser.params or ())(optargs)
        return check_arguments(renamed, subparser.callback)


class Namespace:  # pylint: disable=too-few-public-methods
    """Namespace object that contains:

    - mapping from names to values
    - (optional) command prefix from argv
    """
    def __init__(self, names: dict[str, t.Any], cli: CLInterface):
        self.names = names
        self.cli = cli

    def bind(self, function: t.Callable[..., t.Any]) -> t.Any:
        """Pass names to function."""
        args, kwargs = to_args_kwargs(self.names, function)
        return function(*args, **kwargs)


def check_arguments(optargs: dict[str, t.Any],
                    function: t.Callable[..., t.Any],
                    ) -> dict[str, t.Any]:
    """Check if optargs contains all args that function needs.

    Return optargs if okay.
    Raise MissingArguments if not.
    """
    args, kwargs = to_args_kwargs(optargs, function)
    sig = inspect.signature(function)
    try:
        sig.bind(*args, **kwargs)
        return optargs
    except TypeError as exc:
        raise MissingArgument from exc


Resolver = t.Callable[[t.Any, t.Any], t.Any]


def rename(optargs: list[tuple[str, t.Any]],
           name: str,
           names: set[str],
           resolve: Resolver,
           ) -> list[tuple[str, t.Any]]:
    """Rename parameters in optargs and resolve name conflicts."""
    renamed = []
    none = object()
    final: t.Any = none
    for param, value in optargs:
        if param in names:
            final = value if final is none else resolve(final, value)
        else:
            renamed.append((param, value))
    if final is not none:
        renamed.append((name, final))
    return renamed


class Renamer:  # pylint: disable=too-few-public-methods
    """Options and arguments renamer."""
    def __init__(self, params: t.Sequence[Param]):
        self.params = params

    def __call__(self, optargs: list[tuple[str, t.Any]]) -> dict[str, t.Any]:
        """Rename parameters and convert into dict."""
        for param in self.params:
            optargs = rename(
                optargs,
                param.name,
                set(param.optargs),
                param.resolve
            )
        return dict(optargs)
