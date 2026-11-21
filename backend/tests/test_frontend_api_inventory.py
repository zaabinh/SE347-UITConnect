"""Frontend inventory must prove real, mounted API consumption."""

from collections import Counter
import json
from pathlib import Path
import shutil

import pytest

from app.factory import create_app
from scripts.api_baseline import ROOT
from scripts.render_api_contract import validate_frontend_inventory


@pytest.fixture(scope='module')
def schema():
    return create_app().openapi()


@pytest.fixture
def inventory_root(tmp_path):
    for directory in ('app', 'components', 'lib'):
        shutil.copytree(ROOT / 'frontend' / directory, tmp_path / 'frontend' / directory)
    target = tmp_path / 'backend/tests/frontend_api_inventory.json'
    target.parent.mkdir(parents=True)
    shutil.copy2(ROOT / 'backend/tests/frontend_api_inventory.json', target)
    return tmp_path


def rewrite_inventory(root: Path, change):
    path = root / 'backend/tests/frontend_api_inventory.json'
    inventory = json.loads(path.read_text(encoding='utf-8'))
    change(inventory['operations'])
    path.write_text(json.dumps(inventory, ensure_ascii=False), encoding='utf-8')


def test_inventory_covers_every_operation_with_truthful_status(schema):
    rows = validate_frontend_inventory(schema)
    assert len(rows) == 62
    assert Counter(row['status'] for row in rows) == {
        'Integrated': 47, 'Planned': 2, 'No Consumer': 13,
    }


@pytest.mark.parametrize('change', [
    lambda rows: rows.pop(),
    lambda rows: rows.append(rows[0]),
])
def test_inventory_rejects_missing_or_duplicate_operations(schema, inventory_root, change):
    rewrite_inventory(inventory_root, change)
    with pytest.raises(AssertionError, match='cover every live operation exactly once'):
        validate_frontend_inventory(schema, inventory_root)


def test_inventory_rejects_stale_consumer_reference(schema, inventory_root):
    def change(rows):
        row = next(item for item in rows if item['status'] == 'Integrated')
        row['consumers'][0]['symbol'] = 'missingConsumerCall'

    rewrite_inventory(inventory_root, change)
    with pytest.raises(AssertionError, match='Stale frontend reference'):
        validate_frontend_inventory(schema, inventory_root)


def test_unused_client_declaration_cannot_be_labeled_integrated(schema, inventory_root):
    def change(rows):
        row = next(item for item in rows if item['operation_id'] == 'recommendations_list_collaborative')
        row['status'] = 'Integrated'
        row['consumers'] = list(row['clients'])

    rewrite_inventory(inventory_root, change)
    with pytest.raises(AssertionError, match='Import/declaration alone is not an invocation'):
        validate_frontend_inventory(schema, inventory_root)
