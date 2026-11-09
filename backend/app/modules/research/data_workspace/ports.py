from typing import Protocol

from app.shared.data_workspace_v2 import DatasetRefV2


class TableReadPort(Protocol):
    """Local, full read for future consumers; no physical paths or fabricated files.

    Adapters must validate project, inclusion, all ancestors, content hash and expected
    revision/hash. 409 is stale evidence; unavailable/corrupt stored content is 503.
    The remote adapter will additionally receive an authorized project scope.
    """

    def read_table(
        self,
        project_id: str,
        table_id: str,
        expected_revision: int | None = None,
        expected_hash: str | None = None,
    ) -> tuple[DatasetRefV2, list[list[str | None]]]: ...
