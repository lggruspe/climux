"""Read options and arguments from the command-line."""

import collections
import typing as t


Opts = list[tuple[str, list[str]]]
Args = list[str]
Count = t.Union[int, float]  # float only used for inf


class UnknownOption(ValueError):
    """Unrecognized option."""


class OptArgSpec:  # pylint: disable=too-few-public-methods
    """Description of short and long options (with max argument counts)."""
    def __init__(self,
                 short_options: str,
                 *long_options: str,
                 **counts: Count):
        """count is an upper bound."""
        self.short_options = set(short_options)
        self.long_options = set(long_options)
        self.counts = counts

        for opt in counts:
            if opt not in self.short_options and opt not in self.long_options:
                if len(opt) == 1:
                    self.short_options.add(opt)
                else:
                    self.long_options.add(opt)

        for opt in self.short_options:
            self.counts.setdefault(opt, 0)
        for opt in self.long_options:
            self.counts.setdefault(opt, 0)

        assert all(len(o) > 0 for o in self.counts)

    def expand(self, prefix: str) -> str:
        """Expand long option prefix.

        Raises UnknownOption if prefix is ambiguous or invalid.
        """
        assert not prefix.startswith("-")
        candidates = [o for o in self.long_options if o.startswith(prefix)]
        if len(candidates) != 1:
            raise UnknownOption(f"--{prefix}")
        return candidates[0]


def take(count: Count, deque: collections.deque[str]) -> list[str]:
    """Take up to 'count' items from deque or until the next option.

    Read up to the next option if count is inf.
    """
    args = []
    while deque and not deque[0].startswith("-") and count > 0:
        args.append(deque.popleft())
        count -= 1
    return args


class Reader:  # pylint: disable=too-few-public-methods
    """Argv reader."""
    def __init__(self,
                 short_options: str,
                 *long_options: str,
                 **counts: Count):
        self.spec = OptArgSpec(short_options, *long_options, **counts)

    def read(self, argv: t.Sequence[str]) -> tuple[Opts, Args]:
        """Read options and arguments from argv.

        Assume argv doesn't contain the program name.
        Short and long options also shouldn't start with '-'.
        """
        opts = []
        args = []
        deque = collections.deque(argv)

        while deque:
            current = deque.popleft()
            if current.startswith("--"):
                opt = self.spec.expand(current[2:])
                opts.append((opt, take(self.spec.counts[opt], deque)))
            elif current.startswith("-"):
                for opt in current[1:]:
                    if opt not in self.spec.short_options:
                        raise UnknownOption(f"-{opt}")
                    opts.append((opt, take(self.spec.counts[opt], deque)))
            else:
                args.append(current)

        return opts, args


UsingFunction = t.Callable[[list[str], list[str]], list[str]]


class Merger:
    """Options merger."""
    def __init__(self) -> None:
        self.queue: list[tuple[str, tuple[str, ...], UsingFunction]] = []

    def add(self,
            name: str,
            *names: str,
            using: UsingFunction,
            ) -> "Merger":
        """Add merge handler.

        The first name is used as the canonical option name.
        """
        self.queue.append((name, names, using))
        return self

    @staticmethod
    def _merge_one(opts: Opts,
                   name: str,
                   *names: str,
                   using: UsingFunction,
                   ) -> Opts:
        """Merge options."""
        merged = []
        accumulator: t.Optional[list[str]] = None

        for opt, args in opts:
            if opt == name or opt in names:
                accumulator = (
                    args if accumulator is None else using(accumulator, args)
                )
            else:
                merged.append((opt, args))
        if accumulator is not None:
            merged.append((name, accumulator))
        return merged

    def merge(self, opts: Opts) -> Opts:
        """Merge all options."""
        for name, names, using in self.queue:
            opts = self._merge_one(opts, name, *names, using=using)
        return opts