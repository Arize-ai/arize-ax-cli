"""Onboarding command: set up Arize AX tracing with a coding agent."""

import typer

from ax.core.decorators import handle_errors

app = typer.Typer(
    name="instrument",
    help="Set up Arize AX tracing with your coding agent",
    invoke_without_command=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)


@app.callback(invoke_without_command=True)
@handle_errors
def instrument(ctx: typer.Context) -> None:
    """Set up Arize AX tracing with your coding agent.

    Chooses a coding agent, installs the AX CLI and the Arize skills so the agent
    can use them, then launches it with a guided setup that takes you from Arize
    signup to your first traces.

    Examples:
      ax instrument

      uvx arize-ax-cli instrument    # with nothing installed yet
    """
    if ctx.invoked_subcommand is not None:
        return

    from ax.instrument import run

    code = run()
    if code:
        raise typer.Exit(code)
