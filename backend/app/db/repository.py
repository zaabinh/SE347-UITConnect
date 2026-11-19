"""Persistence primitives; repositories never own a transaction."""

from sqlalchemy.orm import Session


class Repository:
    def __init__(self, session: Session):
        self.session = session

    def query(self, *entities):
        return self.session.query(*entities)

    def add(self, entity):
        self.session.add(entity)
        return entity

    def delete(self, entity):
        self.session.delete(entity)

    def flush(self):
        self.session.flush()

    def refresh(self, entity):
        self.session.refresh(entity)

    def execute(self, *args, **kwargs):
        return self.session.execute(*args, **kwargs)
