"""Run independently of the API: python -m scripts.outbox_worker."""

import argparse
import logging
import signal
from threading import Event

from app.db.outbox import dispatch_one
from app.db.session import SessionLocal, engine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true', help='Dispatch at most one event, then exit.')
    args = parser.parse_args()
    stopped = Event()
    for name in ('SIGINT', 'SIGTERM'):
        signal.signal(getattr(signal, name), lambda *_: stopped.set())
    try:
        while not stopped.is_set():
            try:
                worked = dispatch_one(SessionLocal)
            except Exception:
                # SQL/HTTP exceptions can contain credentials or reset links.
                logging.error('Outbox dispatch failed; retrying without exposing private payloads.')
                if args.once:
                    raise SystemExit(1) from None
                worked = False
            if args.once:
                break
            if not worked:
                stopped.wait(5)
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
