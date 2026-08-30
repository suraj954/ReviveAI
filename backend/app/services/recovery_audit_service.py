from __future__ import annotations

import json
from typing import Any

from app.models.recovery_attempt import RecoveryAttempt
from app.models.recovery_event import RecoveryEvent


class RecoveryAuditService:
    """
    Centralized append-only audit logging for recovery lifecycles.

    RecoveryAttempt stores the current lifecycle state.

    RecoveryEvent stores immutable historical events explaining
    how and why that state was reached.

    All recovery audit events should be created through this service
    rather than scattered directly throughout application code.
    """

    def __init__(self, db) -> None:
        self.db = db

    def record(
        self,
        attempt: RecoveryAttempt,
        *,
        event_type: str,
        description: str,
        metadata: dict[str, Any] | None = None,
    ) -> RecoveryEvent:
        """
        Append an immutable audit event to a recovery attempt.

        Args:
            attempt:
                Recovery attempt the event belongs to.

            event_type:
                Stable machine-readable event identifier.

            description:
                Human-readable explanation of what happened.

            metadata:
                Optional structured context serialized as JSON.

        Returns:
            The persisted RecoveryEvent instance.
        """

        metadata_json = None

        if metadata is not None:
            metadata_json = json.dumps(
                metadata,
                sort_keys=True,
                default=str,
            )

        event = RecoveryEvent(
            recovery_attempt_id=attempt.id,
            event_type=event_type,
            description=description,
            metadata_json=metadata_json,
        )

        self.db.add(event)
        self.db.flush()

        return event

    def record_transition(
        self,
        attempt: RecoveryAttempt,
        *,
        from_status: str | None,
        to_status: str,
        description: str,
        metadata: dict[str, Any] | None = None,
    ) -> RecoveryEvent:
        """
        Record a lifecycle state transition.

        This is a convenience wrapper that standardizes transition
        metadata across the recovery system.
        """

        transition_metadata: dict[str, Any] = {
            "from_status": from_status,
            "to_status": to_status,
        }

        if metadata:
            transition_metadata.update(metadata)

        return self.record(
            attempt,
            event_type="status_transition",
            description=description,
            metadata=transition_metadata,
        )