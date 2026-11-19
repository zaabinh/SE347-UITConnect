"""Generate the single machine-readable contract from FastAPI's route metadata."""

from fastapi.openapi.utils import get_openapi


def configure_openapi(app):
    def openapi():
        if app.openapi_schema is None:
            schema = get_openapi(title=app.title, version=app.version,
                                 description=app.description, routes=app.routes)
            for path, operations in schema['paths'].items():
                for method, operation in operations.items():
                    if method not in {'get', 'post', 'put', 'patch', 'delete', 'head', 'options'}:
                        continue
                    for status, response in operation.get('responses', {}).items():
                        if status.isdigit() and int(status) >= 400:
                            content = response.get('content', {})
                            if 'application/json' in content:
                                content['application/problem+json'] = content.pop('application/json')
                    operation.setdefault('responses', {})
            app.openapi_schema = schema
        return app.openapi_schema
    app.openapi = openapi
