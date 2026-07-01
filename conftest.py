"""
conftest.py at the repository root.

Its presence makes pytest add the project root to sys.path, so the tests in
tests/ can import the pipeline modules (parse_catalog, entities) regardless of
how pytest is run (`pytest`, `python -m pytest`, or from an IDE).
"""
