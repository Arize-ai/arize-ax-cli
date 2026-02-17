"""ASCII art banners for Arize AX CLI."""

from ax.version import __version__

# Option 1: Classic ASCII
OPTION_1 = """
[bold magenta]     _         _              [bold cyan]  _   __  __[/bold cyan] [/bold magenta]
[bold magenta]    / \\   _ __(_)_______     [bold cyan]  / \\  \\ \\/ /[/bold cyan] [/bold magenta]
[bold magenta]   / _ \\ | '__| |_  / _ \\   [bold cyan]  / _ \\  \\  /[/bold cyan] [/bold magenta]
[bold magenta]  / ___ \\| |  | |/ /  __/    [bold cyan]/ ___ \\ /  \\ [/bold cyan] [/bold magenta]
[bold magenta] /_/   \\_\\_|  |_/___\\___|  [bold cyan] /_/   \\_\\_/\\_\\[/bold cyan] [/bold magenta]
[dim cyan]                 AI Observability Platform (v{version})[/dim cyan]"""

# Default banner (can be changed to any option)
DEFAULT_BANNER = OPTION_1.format(version=__version__)
