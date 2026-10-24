"""OpenCode Companion: models, agents, MCP servers, workspaces and settings."""


def main() -> int:
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        from .self_test import run
        return run(sys.argv[2])
    from .app import main as run

    return run()
