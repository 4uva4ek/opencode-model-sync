"""Keep opencode's model list in sync with local and self-hosted model servers."""


def main() -> int:
    from .app import main as run

    return run()
