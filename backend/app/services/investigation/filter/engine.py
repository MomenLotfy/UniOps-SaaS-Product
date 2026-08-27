from __future__ import annotations
from typing import Any, Dict, List, Optional
from sqlalchemy import and_, or_
from sqlalchemy.orm import Query

class FilterEngine:
    """
    The FilterEngine provides a deterministic way to map high-level
    investigation filters to database expressions.
    """

    def __init__(self):
        # Map of operator strings to SQLAlchemy operations
        self._operators = {
            "eq": lambda col, val: col == val,
            "neq": lambda col, val: col != val,
            "gt": lambda col, val: col > val,
            "lt": lambda col, val: col < val,
            "gte": lambda col, val: col >= val,
            "lte": lambda col, val: col <= val,
            "in": lambda col, val: col.in_(val if isinstance(val, list) else [val]),
            "nin": lambda col, val: ~col.in_(val if isinstance(val, list) else [val]),
            "contains": lambda col, val: col.contains(val),
            "startswith": lambda col, val: col.startswith(val),
            "endswith": lambda col, val: col.endswith(val),
            "is_null": lambda col, val: col.is_(None) if val else col.is_not(None),
        }

    def build_filter_expression(self, model: Any, filters: Dict[str, Any]) -> Optional[Any]:
        """
        Transforms a dictionary of filters into a SQLAlchemy expression.

        Expected filter format:
        {
            "risk_score": {"op": "gt", "val": 7.5},
            "owner": {"op": "eq", "val": "Team Alpha"},
            "status": {"op": "in", "val": ["open", "pending"]}
        }
        """
        if not filters:
            return None

        expressions = []

        for field, criteria in filters.items():
            # Handle simple equality (field: value)
            if not isinstance(criteria, dict):
                expressions.append(self._operators["eq"](getattr(model, field), criteria))
                continue

            # Handle structured operator (field: {op: ..., val: ...})
            op_key = criteria.get("op", "eq")
            val = criteria.get("val")

            if op_key in self._operators:
                try:
                    col = getattr(model, field)
                    expressions.append(self._operators[op_key](col, val))
                except AttributeError:
                    # Field doesn't exist on model, skip or log
                    continue
            else:
                # Default to equality if operator is unknown
                try:
                    expressions.append(self._operators["eq"](getattr(model, field), val))
                except AttributeError:
                    continue

        return and_(*expressions) if expressions else None

    def apply_filters(self, query: Query, model: Any, filters: Dict[str, Any]) -> Query:
        """
        Applies the generated filter expression to a SQLAlchemy query.
        """
        expression = self.build_filter_expression(model, filters)
        if expression is not None:
            return query.filter(expression)
        return query
