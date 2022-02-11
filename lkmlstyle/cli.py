import argparse
import pathlib
from rich.markup import escape
from rich.console import Console
from lkmlstyle.check import check


def main():
    console = Console(stderr=True)
    parser = argparse.ArgumentParser(description="A flexible style checker for LookML.")
    parser.add_argument("file", type=pathlib.Path, help="path to the file to check")
    parser.add_argument(
        "--ignore",
        nargs="+",
        metavar="CODE",
        required=False,
        help="rule codes to exclude from checking, like 'D106' or 'M200'",
    )
    args = parser.parse_args()

    with args.file.open("r") as file:
        text = file.read()

    violations = check(text, ignore=args.ignore)

    lines = text.split("\n")

    console.print()
    console.rule(
        f"Found {len(violations)} LookML style issues",
        style="#9999ff",
    )
    console.print()
    for violation in violations:
        code, title, line_number = violation
        console.print(f"{code} [bold red]{title}[/bold red]")
        console.print(f"{args.file}:{line_number}")
        console.rule(style="grey30")

        for n in range(line_number - 1, line_number + 3):
            if n <= 0:
                continue
            if n == line_number:
                console.print(f"{n:<4} >| {escape(lines[n - 1])}", highlight=False)
            else:
                console.print(
                    f"[dim]{n:<4}[/dim]  | [dim]{lines[n - 1]}[/dim]", highlight=False
                )
        console.print()


if __name__ == "__main__":
    main()
