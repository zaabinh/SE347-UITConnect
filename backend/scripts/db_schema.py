"""Read SQL Server catalogs without reading application data or changing schema."""

import json
import re
from decimal import Decimal

from sqlalchemy import text


def quote(name: str) -> str:
    return "[" + name.replace("]", "]]") + "]"


def qualified(schema: str, name: str) -> str:
    return f"{quote(schema)}.{quote(name)}"


def collation_name(name: str) -> str:
    if not re.fullmatch(r'[A-Za-z0-9_]+', name):
        raise ValueError('Invalid SQL Server collation identifier.')
    return name


def rows(connection, sql: str, **params) -> list[dict]:
    return [
        {key: int(value) if isinstance(value, Decimal) else value for key, value in row.items()}
        for row in connection.execute(text(sql), params).mappings()
    ]


def inventory(connection) -> dict:
    if connection.dialect.name != "mssql":
        raise RuntimeError("Schema verification requires SQL Server, not an ORM or SQLite substitute.")
    visible = connection.execute(text("SELECT HAS_PERMS_BY_NAME(DB_NAME(),'DATABASE','VIEW DEFINITION')")).scalar_one()
    if visible != 1:
        raise RuntimeError('VIEW DEFINITION permission is required to verify the complete database schema.')
    tables = rows(connection, """
        SELECT s.name AS [schema], t.name, t.is_memory_optimized, t.temporal_type
        FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id
        WHERE t.is_ms_shipped=0 AND NOT (s.name='dbo' AND t.name='alembic_version')
        ORDER BY s.name,t.name
    """)
    for table in tables:
        name = qualified(table['schema'], table['name'])
        table['columns'] = rows(connection, """
            SELECT c.name, ts.name AS type_schema, ty.name AS [type], c.max_length,
                   c.precision, c.scale, c.is_nullable, c.is_identity,
                   CONVERT(bigint,ic.seed_value) AS identity_seed,
                   CONVERT(bigint,ic.increment_value) AS identity_increment,
                   c.is_computed, cc.definition AS computed_definition, cc.is_persisted,
                   c.collation_name, dc.name AS default_name, dc.definition AS [default],
                   c.is_rowguidcol, c.is_sparse, c.is_filestream, c.generated_always_type,
                   c.encryption_type
            FROM sys.columns c
            JOIN sys.types ty ON ty.user_type_id=c.user_type_id
            JOIN sys.schemas ts ON ts.schema_id=ty.schema_id
            LEFT JOIN sys.identity_columns ic ON ic.object_id=c.object_id AND ic.column_id=c.column_id
            LEFT JOIN sys.computed_columns cc ON cc.object_id=c.object_id AND cc.column_id=c.column_id
            LEFT JOIN sys.default_constraints dc ON dc.object_id=c.default_object_id
            WHERE c.object_id=OBJECT_ID(:name) ORDER BY c.column_id
        """, name=name)
        table['indexes'] = rows(connection, """
            SELECT name,type_desc,is_unique,is_primary_key,is_unique_constraint,
                   filter_definition,is_disabled,fill_factor,is_padded,
                   allow_row_locks,allow_page_locks,ignore_dup_key
            FROM sys.indexes WHERE object_id=OBJECT_ID(:name) AND index_id>0
            ORDER BY name
        """, name=name)
        for index in table['indexes']:
            index['columns'] = rows(connection, """
                SELECT c.name,ic.key_ordinal,ic.is_descending_key,ic.is_included_column
                FROM sys.index_columns ic
                JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id
                JOIN sys.indexes i ON i.object_id=ic.object_id AND i.index_id=ic.index_id
                WHERE ic.object_id=OBJECT_ID(:name) AND i.name=:index
                ORDER BY ic.index_column_id
            """, name=name, index=index['name'])
        table['foreign_keys'] = rows(connection, """
            SELECT name,delete_referential_action_desc AS on_delete,
                   update_referential_action_desc AS on_update,
                   is_disabled,is_not_trusted,is_not_for_replication
            FROM sys.foreign_keys WHERE parent_object_id=OBJECT_ID(:name) ORDER BY name
        """, name=name)
        for foreign_key in table['foreign_keys']:
            foreign_key['columns'] = rows(connection, """
                SELECT pc.name,rs.name AS referred_schema,rt.name AS referred_table,
                       rc.name AS referred_column
                FROM sys.foreign_key_columns fc
                JOIN sys.foreign_keys f ON f.object_id=fc.constraint_object_id
                JOIN sys.columns pc ON pc.object_id=fc.parent_object_id AND pc.column_id=fc.parent_column_id
                JOIN sys.tables rt ON rt.object_id=fc.referenced_object_id
                JOIN sys.schemas rs ON rs.schema_id=rt.schema_id
                JOIN sys.columns rc ON rc.object_id=fc.referenced_object_id AND rc.column_id=fc.referenced_column_id
                WHERE f.parent_object_id=OBJECT_ID(:name) AND f.name=:constraint
                ORDER BY fc.constraint_column_id
            """, name=name, constraint=foreign_key['name'])
        table['checks'] = rows(connection, """
            SELECT name,definition,is_disabled,is_not_trusted,is_not_for_replication
            FROM sys.check_constraints WHERE parent_object_id=OBJECT_ID(:name) ORDER BY name
        """, name=name)
    modules = rows(connection, """
        SELECT s.name AS [schema],o.name,o.type,m.definition
        FROM sys.objects o JOIN sys.schemas s ON s.schema_id=o.schema_id
        LEFT JOIN sys.sql_modules m ON m.object_id=o.object_id
        WHERE o.is_ms_shipped=0 AND o.type IN ('V','TR','P','FN','IF','TF','SO','SN')
        ORDER BY s.name,o.name
    """)
    return {
        'format': 1,
        'collation': connection.execute(text("SELECT CONVERT(nvarchar(128),DATABASEPROPERTYEX(DB_NAME(),'Collation'))")).scalar_one(),
        'tables': tables,
        'modules': modules,
    }


def canonical(snapshot: dict) -> str:
    return json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False) + '\n'


def differences(expected, actual, path='$') -> list[str]:
    if type(expected) is not type(actual):
        return [f'{path}: value/type changed']
    if isinstance(expected, dict):
        result = [f'{path}.{key}: missing/unexpected' for key in sorted(expected.keys() ^ actual.keys())]
        for key in sorted(expected.keys() & actual.keys()):
            result.extend(differences(expected[key], actual[key], f'{path}.{key}'))
        return result
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return [f'{path}: item count {len(expected)} != {len(actual)}']
        return [diff for i, (left, right) in enumerate(zip(expected, actual))
                for diff in differences(left, right, f'{path}[{i}]')]
    return [] if expected == actual else [f'{path}: {expected!r} != {actual!r}']


def column_sql(column: dict) -> str:
    if column['type_schema'] != 'sys' or any(column[k] for k in (
        'is_sparse', 'is_filestream', 'generated_always_type', 'encryption_type'
    )):
        raise RuntimeError(f"Unsupported column feature: {column['name']}; review baseline manually.")
    name = quote(column['name'])
    if column['is_computed']:
        return f"{name} AS {column['computed_definition']}" + (' PERSISTED' if column['is_persisted'] else '')
    kind = column['type']
    if kind in {'nvarchar', 'nchar', 'varchar', 'char', 'varbinary', 'binary'}:
        length = column['max_length']
        length = 'MAX' if length == -1 else length // 2 if kind.startswith('n') else length
        kind += f'({length})'
    elif kind in {'decimal', 'numeric'}:
        kind += f"({column['precision']},{column['scale']})"
    elif kind in {'datetime2', 'datetimeoffset', 'time'}:
        kind += f"({column['scale']})"
    elif kind not in {'bit', 'int', 'bigint', 'smallint', 'tinyint', 'datetime', 'smalldatetime',
                      'date', 'uniqueidentifier', 'money', 'smallmoney', 'real', 'float', 'text', 'ntext', 'image'}:
        raise RuntimeError(f'Unsupported SQL Server type: {kind}')
    result = f'{name} {kind}'
    if column['collation_name']:
        result += ' COLLATE ' + collation_name(column['collation_name'])
    if column['is_identity']:
        result += f" IDENTITY({column['identity_seed']},{column['identity_increment']})"
    if column['is_rowguidcol']:
        result += ' ROWGUIDCOL'
    result += ' NULL' if column['is_nullable'] else ' NOT NULL'
    if column['default'] is not None:
        result += f" CONSTRAINT {quote(column['default_name'])} DEFAULT {column['default']}"
    return result


def index_keys(index: dict) -> str:
    columns = sorted((c for c in index['columns'] if c['key_ordinal']), key=lambda c: c['key_ordinal'])
    return ', '.join(quote(c['name']) + (' DESC' if c['is_descending_key'] else ' ASC') for c in columns)


def render_baseline(snapshot: dict) -> str:
    """Freeze catalog-derived DDL. Never substitute current ORM metadata here."""
    if snapshot['modules']:
        raise RuntimeError('Views/triggers/routines require reviewed DDL before a baseline can be generated.')
    statements = []
    for table in snapshot['tables']:
        if table['is_memory_optimized'] or table['temporal_type'] or table['schema'] != 'dbo':
            raise RuntimeError('Non-dbo, temporal or memory-optimized tables need a reviewed baseline.')
        name = qualified(table['schema'], table['name'])
        definitions = [column_sql(column) for column in table['columns']]
        for index in table['indexes']:
            if index['type_desc'] not in {'CLUSTERED', 'NONCLUSTERED'}:
                raise RuntimeError('Unsupported index type: ' + index['type_desc'])
            if index['is_primary_key'] or index['is_unique_constraint']:
                kind = 'PRIMARY KEY' if index['is_primary_key'] else 'UNIQUE'
                definitions.append(f"CONSTRAINT {quote(index['name'])} {kind} {index['type_desc']} ({index_keys(index)})")
        statements.append(f'CREATE TABLE {name} (\n    ' + ',\n    '.join(definitions) + '\n)')
    for table in snapshot['tables']:
        name = qualified(table['schema'], table['name'])
        for fk in table['foreign_keys']:
            target = fk['columns'][0]
            cols = ', '.join(quote(c['name']) for c in fk['columns'])
            refs = ', '.join(quote(c['referred_column']) for c in fk['columns'])
            trust = 'NOCHECK' if fk['is_not_trusted'] else 'CHECK'
            replication = ' NOT FOR REPLICATION' if fk['is_not_for_replication'] else ''
            statements.append(f"ALTER TABLE {name} WITH {trust} ADD CONSTRAINT {quote(fk['name'])} FOREIGN KEY ({cols}) REFERENCES {qualified(target['referred_schema'], target['referred_table'])} ({refs}) ON DELETE {fk['on_delete'].replace('_',' ')} ON UPDATE {fk['on_update'].replace('_',' ')}{replication}")
            if fk['is_disabled']:
                statements.append(f"ALTER TABLE {name} NOCHECK CONSTRAINT {quote(fk['name'])}")
        for check in table['checks']:
            trust = 'NOCHECK' if check['is_not_trusted'] else 'CHECK'
            replication = ' NOT FOR REPLICATION' if check['is_not_for_replication'] else ''
            statements.append(f"ALTER TABLE {name} WITH {trust} ADD CONSTRAINT {quote(check['name'])} CHECK{replication} {check['definition']}")
            if check['is_disabled']:
                statements.append(f"ALTER TABLE {name} NOCHECK CONSTRAINT {quote(check['name'])}")
        for index in table['indexes']:
            if index['is_primary_key'] or index['is_unique_constraint']:
                continue
            unique = 'UNIQUE ' if index['is_unique'] else ''
            statement = f"CREATE {unique}{index['type_desc']} INDEX {quote(index['name'])} ON {name} ({index_keys(index)})"
            included = [quote(c['name']) for c in index['columns'] if c['is_included_column']]
            if included:
                statement += ' INCLUDE (' + ', '.join(included) + ')'
            if index['filter_definition']:
                statement += ' WHERE ' + index['filter_definition']
            options = [f"FILLFACTOR={index['fill_factor']}"] if index['fill_factor'] else []
            for option, key, default in [('PAD_INDEX','is_padded',False), ('ALLOW_ROW_LOCKS','allow_row_locks',True),
                                          ('ALLOW_PAGE_LOCKS','allow_page_locks',True), ('IGNORE_DUP_KEY','ignore_dup_key',False)]:
                if bool(index[key]) != default:
                    options.append(option + ('=ON' if index[key] else '=OFF'))
            if options:
                statement += ' WITH (' + ', '.join(options) + ')'
            statements.append(statement)
            if index['is_disabled']:
                statements.append(f"ALTER INDEX {quote(index['name'])} ON {name} DISABLE")
    return '\nGO\n\n'.join(statements) + '\nGO\n'


def split_batches(sql: str) -> list[str]:
    batches, current = [], []
    for line in sql.splitlines():
        if line.strip().upper() == 'GO':
            if '\n'.join(current).strip():
                batches.append('\n'.join(current).strip())
            current = []
        else:
            current.append(line)
    if '\n'.join(current).strip():
        batches.append('\n'.join(current).strip())
    return batches
