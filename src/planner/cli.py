from __future__ import annotations

import typer

from planner import __version__

app = typer.Typer(help="Planner CLI", no_args_is_help=True)


@app.callback()
def cli() -> None:
    """Planner CLI."""
    # This callback exists to keep the CLI in group mode.
    return None


@app.command()
def version() -> None:
    """Print the Planner version."""
    typer.echo(__version__)


def main() -> None:
    # This is what the console script should call.
    app()


if __name__ == "__main__":
    main()
