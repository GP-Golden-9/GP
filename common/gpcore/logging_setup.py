"""Structured JSON logging, identical on Pis and the operator laptop.

Every record carries ``run_id`` so one launch session can be correlated
across machines (the same run_id rides in every ZMQ envelope).

Usage:
    from gpcore.logging_setup import new_run_id, setup_logging
    log = setup_logging('robot2_bridge', run_id=os.environ.get('GP_RUN_ID'))
    log.info('serial connected', extra={'kv': {'port': '/dev/mega'}})
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from logging.handlers import RotatingFileHandler

LOG_MAX_BYTES = 2 * 1024 * 1024
LOG_BACKUPS = 5


def new_run_id() -> str:
    """Sortable id: UTC timestamp + 4 random hex chars, e.g. 20260610T1530-3fa1."""
    return time.strftime('%Y%m%dT%H%M', time.gmtime()) + '-' + uuid.uuid4().hex[:4]


class JsonFormatter(logging.Formatter):
    def __init__(self, node: str, run_id: str):
        super().__init__()
        self.node = node
        self.run_id = run_id

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            'ts': time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(record.created))
                  + f'.{int(record.msecs):03d}',
            'level': record.levelname,
            'node': self.node,
            'run_id': self.run_id,
            'event': record.getMessage(),
        }
        kv = getattr(record, 'kv', None)
        if isinstance(kv, dict):
            entry.update(kv)
        if record.exc_info and record.exc_info[0] is not None:
            entry['exc'] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False, default=str)


def setup_logging(node: str, *, run_id: str | None = None,
                  log_dir: str | None = None,
                  level: int = logging.INFO) -> logging.Logger:
    """Configure and return a logger for one node/process.

    * stdout: JSON lines (systemd/journald captures these on the Pis)
    * file:   <log_dir>/<run_id>/<node>.log, rotating 5×2 MB (if log_dir given;
              defaults to $GP_LOG_DIR or ~/gp_logs)
    """
    run_id = run_id or os.environ.get('GP_RUN_ID') or new_run_id()
    log_dir = log_dir or os.environ.get('GP_LOG_DIR') or os.path.join(
        os.path.expanduser('~'), 'gp_logs')

    logger = logging.getLogger(f'gp.{node}')
    logger.setLevel(level)
    logger.propagate = False
    logger.handlers.clear()

    formatter = JsonFormatter(node, run_id)

    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    logger.addHandler(stream)

    try:
        session_dir = os.path.join(log_dir, run_id)
        os.makedirs(session_dir, exist_ok=True)
        fileh = RotatingFileHandler(os.path.join(session_dir, f'{node}.log'),
                                    maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUPS,
                                    encoding='utf-8')
        fileh.setFormatter(formatter)
        logger.addHandler(fileh)
    except OSError as exc:  # read-only FS etc. — keep running on stdout only
        logger.warning('file logging disabled', extra={'kv': {'reason': str(exc)}})

    logger.run_id = run_id  # convenience attribute
    return logger
