"""One application use case owns the session transaction, including auth reads."""

from sqlalchemy.orm import Session


class UnitOfWork:
    def __init__(self, session: Session):
        self.session = session

    def __enter__(self):
        if self.session.info.get('unit_of_work'):
            raise RuntimeError('Nested units of work must share the outer transaction.')
        self.session.info['unit_of_work'] = self
        return self

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
