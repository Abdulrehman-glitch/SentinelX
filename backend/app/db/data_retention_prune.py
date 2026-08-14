"""Enforce the retention periods that data_retention_report only reports on.

Run (safe by default — reports what it *would* delete and exits):
    python -m app.db.data_retention_prune
    python -m app.db.data_retention_prune --execute

Neon's free tier is capped on storage, not compute, and system_metrics grows by
~8,640 rows per device per day. Something has to delete old rows or the database
fills. This is that something: a plain CLI, so it needs no always-on worker and
no paid scheduler. Point a monthly CI job or a manual run at it.

Deletion is deliberately awkward to do by accident:
  * dry-run is the default; --execute is required to remove anything,
  * work happens in bounded batches so a mistake is interruptible rather than
    one enormous unkillable transaction,
  * --max-batches caps the blast radius of a single invocation.
"""

import argparse
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select

from app.db.data_retention_report import RETENTION_RULES, RetentionRule
from app.db.session import SessionLocal

DEFAULT_BATCH_SIZE = 5_000
DEFAULT_MAX_BATCHES = 200


def _rules_for(only: str | None) -> list[RetentionRule]:
    if only is None:
        return list(RETENTION_RULES)
    matched = [rule for rule in RETENTION_RULES if rule.label == only]
    if not matched:
        known = ", ".join(rule.label for rule in RETENTION_RULES)
        raise SystemExit(f"Unknown table {only!r}. Known tables: {known}")
    return matched


def prune(
    *,
    execute: bool = False,
    only: str | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_batches: int = DEFAULT_MAX_BATCHES,
) -> list[dict]:
    """Delete rows older than each table's retention period.

    Returns one summary row per table. With execute=False nothing is written and
    the count lands in "would_delete" instead of "deleted".
    """
    if batch_size < 1:
        raise SystemExit("--batch-size must be at least 1.")

    now = datetime.now(timezone.utc)
    results: list[dict] = []

    with SessionLocal() as session:
        for rule in _rules_for(only):
            table = rule.timestamp_column.class_
            cutoff = now - timedelta(days=rule.retention_days)

            eligible = (
                session.scalar(
                    select(func.count())
                    .select_from(table)
                    .where(rule.timestamp_column < cutoff)
                )
                or 0
            )

            deleted = 0
            truncated = False

            if execute and eligible:
                for _ in range(max_batches):
                    # Delete by primary key from a LIMITed subquery: bounded work
                    # per statement, so locks stay short even on a large table.
                    doomed = (
                        select(table.id)
                        .where(rule.timestamp_column < cutoff)
                        .limit(batch_size)
                        .scalar_subquery()
                    )
                    removed = session.execute(
                        delete(table).where(table.id.in_(doomed))
                    ).rowcount
                    session.commit()

                    deleted += removed
                    if removed < batch_size:
                        break
                else:
                    truncated = True

            results.append(
                {
                    "table": rule.label,
                    "retention_days": rule.retention_days,
                    "cutoff": cutoff.isoformat(),
                    "eligible": eligible,
                    "deleted": deleted if execute else 0,
                    "would_delete": 0 if execute else eligible,
                    "truncated": truncated,
                }
            )

    return results


def _print(rows: list[dict], *, execute: bool) -> None:
    header = "Deleted" if execute else "Would delete"
    print(f"{'Table':<28} {'Retention':>10} {'Eligible':>10} {header:>14}")
    print("-" * 66)
    for row in rows:
        count = row["deleted"] if execute else row["would_delete"]
        flag = "  (batch cap hit — run again)" if row["truncated"] else ""
        print(
            f"{row['table']:<28} {row['retention_days']:>9}d "
            f"{row['eligible']:>10} {count:>14}{flag}"
        )
    if not execute:
        print("\nDry run — nothing was deleted. Re-run with --execute to apply.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply SentinelX data retention periods.")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete. Without this the command only reports.",
    )
    parser.add_argument("--table", default=None, help="Restrict to one table label.")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--max-batches", type=int, default=DEFAULT_MAX_BATCHES)
    args = parser.parse_args()

    rows = prune(
        execute=args.execute,
        only=args.table,
        batch_size=args.batch_size,
        max_batches=args.max_batches,
    )
    _print(rows, execute=args.execute)


if __name__ == "__main__":
    main()
