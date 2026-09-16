"""Checks over the repository's own pages, not over a use case.

``links`` walks every Markdown and HTML file for relative links and
fragments; ``commands`` extracts and runs the command lines the
learning pages show. Both are plain modules with a ``main()``, run
either through pytest (``test_links.py``, ``test_commands.py``) or
directly (``uv run python -m cedar_osdc.checks.links``).
"""
