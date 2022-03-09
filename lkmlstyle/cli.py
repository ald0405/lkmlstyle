import argparse
import pathlib
from rich.markup import escape
from rich.markdown import Markdown
from rich.console import Console
from rich.table import Table
from lkmlstyle.check import check
from lkmlstyle.rules import ALL_RULES


console = Console()


def print_rules_table() -> None:
    table = Table(title="lkmlstyle Rules", show_lines=True)
    table.add_column("Code", justify="center")
    table.add_column("Rationale")

    for rule in sorted(ALL_RULES, key=lambda x: x.code):
        table.add_row(rule.code, Markdown(f"**{rule.title}**\n\n{rule.rationale}"))

    console.print(table)


def check_style(args) -> None:
    paths = []
    for path in args.path:
        if path.is_dir():
            paths.extend(path.glob("**/*.lkml"))
        else:
            paths.append(path)

    console.print()
    for path in sorted(set(paths)):
        violations = []
        with path.open("r") as file:
            text = file.read()
        violations.extend(
            check(text, select=tuple(args.select), ignore=tuple(args.ignore))
        )
        lines = text.split("\n")

        if violations:
            console.rule(path.name, style="#9999ff")
            console.print()
        for violation in violations:
            code, title, rationale, line_number = violation
            console.print(f"[{code}] [bold red]{title}[/bold red]")
            console.print(f"{path}:{line_number}")
            if args.show_rationale:
                console.rule(style="grey30")
                console.print(
                    Markdown("**Rationale:** " + rationale),
                    width=80,
                    highlight=False,
                    style="grey50",
                )
            console.rule(style="grey30")

            for i, n in enumerate(range(line_number - 1, line_number + 3)):
                if n <= 0:
                    continue
                # Don't print whitespace-only leading lines
                elif i == 0 and lines[n - 1].strip() == "":
                    continue
                elif n == line_number:
                    console.print(
                        f" {n:<4} [red]>[/red]| {escape(lines[n - 1])}",
                        highlight=False,
                        no_wrap=True,
                    )
                else:
                    console.print(
                        f" [dim]{n:<4}[/dim]  | [dim]{lines[n - 1]}[/dim]",
                        highlight=False,
                        no_wrap=True,
                    )
            console.print()


def main():
    parser = argparse.ArgumentParser(
        description=(
            "A flexible style checker for LookML. "
            "Run `lkmlstyle rules` to see all available rules."
        )
    )
    parser.add_argument(
        "path",
        nargs="*",
        type=pathlib.Path,
        help="path(s) to the file or directory to check",
    )
    parser.add_argument(
        "--ignore",
        nargs="+",
        metavar="CODE",
        required=False,
        help="rule codes to exclude from checking, like 'D106' or 'M200'",
        default=[],
    )
    parser.add_argument(
        "--select",
        nargs="+",
        metavar="CODE",
        required=False,
        help="only check the specified rule codes, like 'D106' or 'M200'",
        default=[],
    )
    parser.add_argument(
        "--show-rationale",
        action="store_true",
        help="for each violation, describe why the rule exists",
    )
    args = parser.parse_args()
    # This is a bit of a hack, but it's tough to get subparsers and positional args
    # to work together without adding something like `lkmlstyle check`.
    try:
        first_positional = str(args.path[0])
    except IndexError:
        pass
    else:
        if first_positional == "rules":
            print_rules_table()
        else:
            check_style(args)


if __name__ == "__main__":
    main()
