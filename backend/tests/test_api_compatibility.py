"""Real oasdiff regressions: regenerated docs must not bless breaking contracts."""

from copy import deepcopy
from hashlib import sha256
import json

import pytest

from app.factory import create_app
from scripts.api_baseline import ROOT, canonical
from scripts.check_api_compatibility import compare, read_trusted_baseline
from scripts.check_api_contract import validate_documentation, validate_implementation
from scripts.render_api_contract import render, validate_examples


@pytest.fixture
def baseline():
    return json.loads((ROOT / 'docs/openapi/candidate-v1.json').read_text(encoding='utf-8'))


def result_for(tmp_path, baseline, current):
    before, after = tmp_path / 'before.json', tmp_path / 'after.json'
    before.write_bytes(canonical(baseline))
    after.write_bytes(canonical(current))
    return compare(before, after)


def test_candidate_matches_recorded_source_hash_and_current_api(tmp_path, baseline):
    path = ROOT / 'docs/openapi/candidate-v1.json'
    metadata = json.loads(path.with_name('candidate-v1.metadata.json').read_text(encoding='utf-8'))
    assert metadata['status'] == 'candidate' and metadata['approval'] is None
    assert sha256(path.read_bytes()).hexdigest() == metadata['sha256']
    assert result_for(tmp_path, baseline, create_app().openapi()).returncode == 0


def test_minlength_breaks_even_when_implementation_docs_and_fingerprint_agree(tmp_path, baseline):
    app = create_app()
    schema = app.openapi()
    assert baseline['components']['schemas']['CreatePostRequest']['properties']['title']['minLength'] == 5
    schema['components']['schemas']['CreatePostRequest']['properties']['title']['minLength'] = 6
    # Consistency alone accepts the intentionally modified schema and regenerated docs.
    validate_implementation(app)
    validate_examples(schema)
    document = tmp_path / 'API_CONTRACT.md'
    document.write_text(render(schema), encoding='utf-8')
    validate_documentation(schema, document)
    result = result_for(tmp_path, baseline, schema)
    assert result.returncode != 0, result.stdout
    assert 'min-length' in result.stdout.lower(), result.stdout


def test_additive_optional_response_field_is_backward_compatible(tmp_path, baseline):
    current = deepcopy(baseline)
    current['components']['schemas']['PostResponse']['properties']['optional_summary'] = {'type': 'string'}
    result = result_for(tmp_path, baseline, current)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('change', [
    'endpoint', 'method', 'required-request', 'parameter-type', 'response-field',
    'response-type', 'security', 'request-content-type', 'response-content-type', 'request-enum', 'response-enum',
])
def test_other_contract_breaks_are_detected(tmp_path, baseline, change):
    current = deepcopy(baseline)
    if change == 'endpoint':
        del current['paths']['/api/v1/feed']
    elif change == 'method':
        del current['paths']['/api/v1/posts/{post_id}']['patch']
    elif change == 'required-request':
        schema = current['components']['schemas']['CreatePostRequest']
        schema['properties']['new_required_field'] = {'type': 'string'}
        schema['required'].append('new_required_field')
    elif change == 'parameter-type':
        parameter = next(item for item in current['paths']['/api/v1/feed']['get']['parameters'] if item['name'] == 'mode')
        parameter['schema'] = {'type': 'integer'}
    elif change == 'response-field':
        schema = current['components']['schemas']['PostResponse']
        del schema['properties']['title']
        schema['required'].remove('title')
    elif change == 'response-type':
        current['components']['schemas']['PostResponse']['properties']['title'] = {'type': 'integer'}
    elif change == 'security':
        current['paths']['/api/v1/auth/login']['post']['security'] = [{'HTTPBearer': []}]
    elif change == 'request-content-type':
        content = current['paths']['/api/v1/posts']['post']['requestBody']['content']
        content['text/plain'] = content.pop('application/json')
    elif change == 'response-content-type':
        content = current['paths']['/api/v1/posts']['post']['responses']['201']['content']
        content['text/plain'] = content.pop('application/json')
    elif change == 'request-enum':
        for value, names in ((baseline, ['A', 'B']), (current, ['A'])):
            value['components']['schemas']['CreatePostRequest']['properties']['title']['enum'] = names
    elif change == 'response-enum':
        # Expanding response values can break exhaustive clients; narrowing requests also breaks callers.
        for value, names in ((baseline, ['A']), (current, ['A', 'B'])):
            value['components']['schemas']['PostResponse']['properties']['title']['enum'] = names
    result = result_for(tmp_path, baseline, current)
    assert result.returncode != 0, f'{change}: {result.stdout} {result.stderr}'


@pytest.mark.parametrize('revision', ['', 'HEAD', 'develop', 'abc'])
def test_release_gate_refuses_missing_or_mutable_trust_reference(revision):
    with pytest.raises(ValueError, match='immutable commit'):
        read_trusted_baseline(revision)


def test_release_gate_reads_git_revision_not_pr_worktree(monkeypatch, baseline):
    from scripts import check_api_compatibility as checker
    data = canonical(baseline)
    metadata = canonical({'status': 'approved', 'source_commit': 'a' * 40, 'sha256': sha256(data).hexdigest()})
    calls = []
    def trusted_git(*arguments):
        calls.append(arguments)
        return metadata if arguments[-1].endswith('.metadata.json') else data
    monkeypatch.setattr(checker, 'git', trusted_git)
    assert read_trusted_baseline('b' * 40) == data
    assert all(arguments[0] == 'show' and arguments[1].startswith('b' * 40 + ':') for arguments in calls)


def test_candidate_is_not_an_approved_baseline(monkeypatch):
    from scripts import check_api_compatibility as checker
    monkeypatch.setattr(checker, 'git', lambda *args: canonical({'status': 'candidate'}))
    with pytest.raises(ValueError, match='approved status'):
        read_trusted_baseline('a' * 40)
