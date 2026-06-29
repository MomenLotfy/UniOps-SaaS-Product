"""
Sprint 3 R35 — BaseLifecycleManager.

Generic state-transition contract used by the three lifecycle managers
(Strategy / Approval / Execution).  Concrete classes keep their public
``can_transition`` / ``transition`` signatures; the base provides:

  - A canonical ``TransitionRule`` value object that records ``from``,
    ``to``, and ``allowed``.
  - A ``validate`` helper that consults the transition map and raises
    a typed exception when the transition is not allowed.
  - A metric-emit hook (``_emit_transition_metric``) that increments
    the Prometheus ``STATE_TRANSITIONS`` counter on every successful
    transition.  The hook is a no-op when observability isn't wired.

The Decision engine does not currently use a lifecycle manager — its
state machine lives inside the pipeline — so this base is only
adopted by the three modules that need it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class TransitionRule:
    """Allowed (from_state, to_state) pair."""

    from_state: str
    to_state: str

    def matches(self, from_state: str, to_state: str) -> bool:
        return self.from_state == from_state and self.to_state == to_state


class BaseLifecycleManager:
    """
    Validate state transitions against an explicit transition map.

    Subclasses set ``VALID_TRANSITIONS`` to a Mapping[str, Iterable[str]]
    (or anything iterable per source state).  Subclasses can also
    override ``_emit_transition_metric`` to push the event to whatever
    observability stack is active; the default is a no-op.
    """

    VALID_TRANSITIONS: Mapping[str, Iterable[str]] = {}

    def can_transition(self, from_state: str, to_state: str) -> bool:
        allowed = self.VALID_TRANSITIONS.get(from_state, ())
        return any(rule.matches(from_state, to_state) for rule in self._normalize_rules(allowed))

    def _normalize_rules(self, target_states: Iterable[str]) -> Iterable[TransitionRule]:
        for s in target_states:
            if isinstance(s, TransitionRule):
                yield s
            else:
                yield TransitionRule(from_state="*", to_state=str(s))

    def validate(self, from_state: str, to_state: str) -> None:
        """
        Raise ``InvalidStateTransitionError`` (or subclass-specific
        equivalent) when the transition is not allowed.

        Subclasses override this method to raise their own typed
        exception.  The base implementation uses a generic ``ValueError``
        to avoid importing concrete exceptions at module load time.
        """
        if not self.can_transition(from_state, to_state):
            raise ValueError(
                f"Illegal transition: {from_state!r} -> {to_state!r}. "
                f"Allowed from {from_state!r}: "
                f"{list(self.VALID_TRANSITIONS.get(from_state, []))}"
            )

    def _emit_transition_metric(
        self,
        entity: str,
        from_state: str | None,
        to_state: str,
    ) -> None:
        """
        Hook for observability.  Default: no-op.  Concrete subclasses
        override this to push to the Prometheus registry.
        """
        return None


__all__ = ["BaseLifecycleManager", "TransitionRule"]
