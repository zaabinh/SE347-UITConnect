"""One application use case owns the session transaction, including auth reads."""

from sqlalchemy.orm import Session
from sqlalchemy import text
from hashlib import sha256
from app.core.exceptions import ApplicationError


class UnitOfWork:
    def __init__(self, session: Session):
        self.session = session

    def __enter__(self):
        if self.session.info.get('unit_of_work'):
            raise RuntimeError('Nested units of work must share the outer transaction.')
        self.session.info['unit_of_work'] = self
        return self

    def lock(self, resource: str):
        """Serialize a SQL Server aggregate's writes without changing its schema."""
        if self.session.get_bind().dialect.name == 'mssql':
            result = self.session.execute(text('''
                SET NOCOUNT ON;
                DECLARE @result int;
                EXEC @result=sys.sp_getapplock @Resource=:resource,
                    @LockMode='Exclusive', @LockOwner='Transaction', @LockTimeout=10000;
                SET NOCOUNT OFF;
                SELECT @result;
            '''), {'resource': 'uitconnect:aggregate:' + sha256(resource.encode()).hexdigest()}).scalar_one()
            if result < 0:
                raise ApplicationError(409, 'The resource is being changed; retry the request.', 'CONCURRENT_MODIFICATION')

    def __exit__(self, exc_type, exc, traceback):
        try:
            if exc_type is not None:
                self.session.rollback()
            else:
                try:
                    self.session.commit()
                except BaseException:
                    self.session.rollback()
                    raise
        finally:
            self.session.info.pop('unit_of_work', None)
        return False
