"""Explicit bounded retention for synthetic decisions; dry-run unless --apply is passed."""
import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from src.database import RiskEvaluation, get_engine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--days', type=int, default=30)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.days <= 365:
        parser.error('days must be between 1 and 365')
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
    with Session(get_engine()) as session, session.begin():
        query = RiskEvaluation.created_at < cutoff
        count = session.scalar(select(func.count()).select_from(RiskEvaluation).where(query))
        if args.apply:
            session.execute(delete(RiskEvaluation).where(query))
        print(('Deleted' if args.apply else 'Would delete'), count, 'expired evaluations and dependent synthetic cases/audit/idempotency records')


if __name__ == '__main__':
    main()
