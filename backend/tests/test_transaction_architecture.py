"""Guard the ownership boundary that caused partial writes in routers."""

import ast
from pathlib import Path

MODULES = Path(__file__).resolve().parents[1] / 'app' / 'modules'


def calls(path):
    return [node for node in ast.walk(ast.parse(path.read_text(encoding='utf-8')))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)]


def test_domain_modules_never_commit_or_rollback():
    violations = [f'{path.relative_to(MODULES)}:{call.lineno}'
                  for path in MODULES.rglob('*.py') for call in calls(path)
                  if call.func.attr in {'commit', 'rollback'}]
    assert violations == []


def test_routers_and_applications_do_not_construct_database_queries():
    paths = [path for path in MODULES.rglob('*.py')
             if path.name.endswith('router.py') or path.name == 'application.py']
    violations = [f'{path.relative_to(MODULES)}:{call.lineno}'
                  for path in paths for call in calls(path)
                  if call.func.attr in {'query', 'execute', 'commit', 'rollback', 'begin', 'begin_nested'}]
    assert violations == []
