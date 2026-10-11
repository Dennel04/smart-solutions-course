"""Atom serial message -> validated high-level executor -> Atom result."""

from __future__ import annotations

import argparse
from pathlib import Path

from .executor import Lab1LetterCatalog, LetterExecutor, MockLetterExecutor
from .models import MessageValidationError, StationResult, parse_atom_message, parse_json_line
from .serial_transport import run_serial_forever
from .station_store import StationJobStore


DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "station_jobs.sqlite3"


class StationAdapter:
    def __init__(
        self,
        store: StationJobStore,
        *,
        executor: LetterExecutor | None = None,
        catalog: Lab1LetterCatalog | None = None,
        local_execution_enabled: bool = False,
    ) -> None:
        self.store = store
        self.executor = executor or MockLetterExecutor()
        self.catalog = catalog or Lab1LetterCatalog()
        self.local_execution_enabled = local_execution_enabled

    def handle_line(self, line: str | bytes) -> str:
        try:
            payload, _ = parse_json_line(line)
            job = parse_atom_message(payload)
        except MessageValidationError as error:
            return StationResult(error.job_id, "refused", error.reason).to_json_line()

        decision = self.store.claim(job)
        if decision.action != "execute":
            assert decision.result is not None
            return decision.result.to_json_line()

        if not self.local_execution_enabled or not self.executor.ready:
            result = StationResult(job.job_id, "refused", "robot_not_enabled")
        elif not self.catalog.supports(job.letter):
            result = StationResult(job.job_id, "refused", "invalid_letter")
        else:
            try:
                outcome = self.executor.execute_letter(
                    job.letter,
                    job.job_id,
                    session=job.session,
                    seq=job.seq,
                    atom_sent_ms=job.atom_sent_ms,
                )
                result = StationResult(job.job_id, outcome.status, outcome.reason)
            except Exception:
                result = StationResult(job.job_id, "refused", "execution_failed")

        self.store.finish(result)
        return result.to_json_line()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="Atom USB port, for example COM4")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--database", default=str(DEFAULT_DB))
    parser.add_argument(
        "--allow-mock-jobs",
        action="store_true",
        help="allow only the software mock executor; this never enables MG400",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    adapter = StationAdapter(
        StationJobStore(args.database),
        executor=MockLetterExecutor(),
        local_execution_enabled=args.allow_mock_jobs,
    )
    run_serial_forever(args.port, args.baud, adapter)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
