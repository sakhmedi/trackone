"""
conftest.py в корне репозитория.

Его наличие заставляет pytest добавить корень проекта в sys.path, поэтому
тесты в tests/ могут импортировать модули пайплайна (parse_catalog, entities)
независимо от того, как запущен pytest (`pytest`, `python -m pytest`, из IDE).
"""
