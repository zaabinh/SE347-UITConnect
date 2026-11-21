"""Validate implemented OpenAPI against the frozen migration map and documentation."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

from fastapi.openapi.models import OpenAPI
from fastapi.routing import APIRoute

BACKEND = Path(__file__).resolve().parents[1]
REPOSITORY = BACKEND.parent
METHODS = {'get', 'post', 'put', 'patch', 'delete', 'head', 'options'}


def frozen_contract():
    return json.loads((BACKEND / 'tests/api_v1_contract.json').read_text(encoding='utf-8'))


def schema_name(schema):
    if '$ref' in schema:
        return schema['$ref'].rsplit('/', 1)[-1]
    if schema.get('type') == 'array':
        return schema_name(schema['items']) + '[]'
    return None


def contract_projection(schema):
    """Contract facts hashed in the document; descriptions/examples may be edited."""
    return {
        'endpoints': [dict(method=method.upper(), path=path,
                           **{key: operation.get(key) for key in
                              ('operationId', 'parameters', 'requestBody', 'responses', 'security')})
                      for path, operations in sorted(schema['paths'].items())
                      for method, operation in sorted(operations.items()) if method in METHODS],
        'schemas': schema.get('components', {}).get('schemas', {}),
        'securitySchemes': schema.get('components', {}).get('securitySchemes', {}),
    }


def contract_digest(schema):
    data = json.dumps(contract_projection(schema), sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return sha256(data.encode()).hexdigest()


def validate_references(schema):
    def walk(value):
        if isinstance(value, dict):
            if '$ref' in value:
                reference = value['$ref']
                assert reference.startswith('#/'), f'Unreviewed external reference: {reference}'
                target = schema
                for part in reference[2:].split('/'):
                    target = target[part.replace('~1', '/').replace('~0', '~')]
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    walk(schema)


def validate_implementation(app):
    schema = app.openapi()
    OpenAPI.model_validate(schema)
    validate_references(schema)
    registered = [(method, route.path) for route in app.routes if isinstance(route, APIRoute)
                  for method in route.methods]
    assert len(registered) == len(set(registered)), 'Duplicate runtime method/path registration'
    routes = [route for route in app.routes if isinstance(route, APIRoute)]
    assert all(route.operation_id for route in routes), 'Every REST route must declare operation_id'
    ids = [route.operation_id for route in routes]
    assert len(ids) == len(set(ids)), 'Duplicate declared operation ID'
    expected = frozen_contract()['endpoints']
    actual = {(method.upper(), path): operation for path, operations in schema['paths'].items()
              for method, operation in operations.items() if method in METHODS}
    expected_keys = {(item['method'], item['path']) for item in expected}
    assert set(actual) == expected_keys | {('GET', '/'), ('GET', '/health')}, 'Endpoint inventory differs from frozen contract'
    for item in expected:
        operation = actual[item['method'], item['path']]
        label = f"{item['method']} {item['path']}"
        assert operation['operationId'] == item['operation_id'], label + ' operation_id'
        responses = operation['responses']
        success = {code for code in responses if code.isdigit() and 200 <= int(code) < 400}
        assert success == {str(item['status'])}, label + ' success status'
        response = responses[str(item['status'])]
        content = response.get('content', {})
        if item['response'] is None:
            assert not content, label + ' must be bodyless/redirect'
        else:
            assert schema_name(content['application/json']['schema']) == item['response'], label + ' response DTO'
        request = operation.get('requestBody')
        if item['request'] is None:
            assert request is None, label + ' unexpected body'
        elif item['request'] == 'multipart:file':
            multipart = request['content']['multipart/form-data']['schema']
            definition = schema['components']['schemas'][schema_name(multipart)]
            file = definition['properties']['file']
            assert file['type'] == 'string', label
            assert file.get('format') == 'binary' or file.get('contentMediaType') == 'application/octet-stream', label
            assert 'file' in definition['required'], label
        else:
            body_schema = request['content']['application/json']['schema']
            if 'anyOf' in body_schema:
                body_schema = next(part for part in body_schema['anyOf'] if '$ref' in part)
            assert schema_name(body_schema) == item['request'], label + ' request DTO'
        assert bool(operation.get('security')) == (item['security'] != 'public'), label + ' security'
        for code in ('400', '401', '403', '404', '409', '422', '429', '500'):
            problem = responses[code]['content']
            assert set(problem) == {'application/problem+json'}, label + ' error media type'
            assert schema_name(problem['application/problem+json']['schema']) == 'ProblemDetails', label
    components = schema['components']['schemas']
    public_fields = set(frozen_contract()['conventions']['public_author_fields'])
    assert set(components['PublicUserSummary']['properties']) == public_fields
    for name in ('PostResponse', 'CommentResponse'):
        assert schema_name(components[name]['properties']['author']) == 'PublicUserSummary'
    return schema


def validate_documentation(schema, document=None):
    from scripts.render_api_contract import render_frontend_inventory, validate_frontend_inventory

    path = document or REPOSITORY / 'docs/API_CONTRACT.md'
    text = Path(path).read_text(encoding='utf-8')
    marker = re.search(r'<!-- OPENAPI_CONTRACT_SHA256: ([0-9a-f]{64}) -->', text)
    assert marker and marker.group(1) == contract_digest(schema), 'Documentation contract facts are stale'
    # A summary row and a detailed section identify every implemented operation.
    for path, operations in schema['paths'].items():
        for method, operation in operations.items():
            if method in METHODS:
                assert f'`{method.upper()} {path}`' in text, f'Undocumented endpoint: {method} {path}'
                assert f"`{operation['operationId']}`" in text, 'Missing operation ID in documentation'
    for name, definition in schema.get('components', {}).get('schemas', {}).items():
        assert f'`{name}`' in text, f'Undocumented schema: {name}'
        for field in definition.get('properties', {}):
            assert f'`{field}`' in text, f'Undocumented field: {name}.{field}'
    validate_frontend_inventory(schema)
    for line in render_frontend_inventory(schema).splitlines():
        if line.startswith('|'):
            assert line in text, 'Frontend consumer inventory is stale'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-docs', action='store_true')
    parser.add_argument('--export', type=Path, help='Export generated OpenAPI; no database connection is opened.')
    args = parser.parse_args()
    from app.factory import create_app
    schema = validate_implementation(create_app())
    if args.check_docs:
        validate_documentation(schema)
    if args.export:
        args.export.parent.mkdir(parents=True, exist_ok=True)
        args.export.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    count = sum(method in METHODS for operations in schema['paths'].values() for method in operations)
    print(f'Validated {count} REST operations; frozen v1 mapping, DTOs, security and OpenAPI references match.')
    if args.check_docs:
        print('API_CONTRACT.md coverage and schema/status/security fingerprint match generated OpenAPI.')


if __name__ == '__main__':
    main()
