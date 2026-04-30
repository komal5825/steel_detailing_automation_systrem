from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.config.settings import settings


@dataclass(frozen=True)
class FieldDefinition:
    field_code: str
    standard_field_name: str
    data_type: str | None
    unit: str | None


class FieldDictionary:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path or settings.master_db_path)
        if not self.db_path.is_absolute():
            self.db_path = Path.cwd() / self.db_path
        self._fields_by_code: dict[str, FieldDefinition] = {}
        self._alias_index: dict[str, FieldDefinition] = {}
        self._load()

    def resolve(self, raw_name: str) -> FieldDefinition | None:
        key = self.clean_key(raw_name)
        if not key:
            return None
        exact = self._alias_index.get(key)
        if exact:
            return exact

        matches = [
            definition
            for alias_key, definition in self._alias_index.items()
            if key in alias_key or alias_key in key
        ]
        unique = {match.field_code: match for match in matches}
        if len(unique) == 1:
            return next(iter(unique.values()))

        if unique:
            return sorted(unique.values(), key=lambda item: len(item.standard_field_name))[0]
        return None

    def normalize_field(self, parsed_field: dict) -> dict:
        definition = self.resolve(parsed_field.get("field_name", ""))
        if not definition:
            return parsed_field

        normalized = dict(parsed_field)
        normalized["field_code"] = definition.field_code
        normalized["field_name"] = definition.standard_field_name
        normalized["unit"] = definition.unit or parsed_field.get("unit")
        normalized["normalized_value"] = self.normalize_value(
            parsed_field.get("normalized_value", parsed_field.get("raw_value", "")),
            definition,
        )
        normalized["confidence"] = min(int(parsed_field.get("confidence", 0)) + 5, 100)
        return normalized

    def _load(self) -> None:
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            fields = connection.execute(
                """
                SELECT field_code, standard_field_name, legacy_aliases, data_type, unit
                FROM field_master
                """
            ).fetchall()
            for row in fields:
                definition = FieldDefinition(
                    field_code=row["field_code"],
                    standard_field_name=row["standard_field_name"],
                    data_type=row["data_type"],
                    unit=row["unit"],
                )
                self._fields_by_code[definition.field_code] = definition
                self._index_alias(definition.standard_field_name, definition)
                for alias in self._split_aliases(row["legacy_aliases"]):
                    self._index_alias(alias, definition)

            aliases = connection.execute(
                """
                SELECT a.field_code, a.alias_name
                FROM alias_master a
                WHERE COALESCE(a.active_flag, 1) = 1
                """
            ).fetchall()
            for row in aliases:
                definition = self._fields_by_code.get(row["field_code"])
                if definition:
                    self._index_alias(row["alias_name"], definition)

    def _index_alias(self, alias: str | None, definition: FieldDefinition) -> None:
        key = self.clean_key(alias or "")
        if key:
            self._alias_index[key] = definition

    def _split_aliases(self, aliases: str | None) -> list[str]:
        if not aliases:
            return []
        return [part.strip() for part in re.split(r"[,|;/]", aliases) if part.strip()]

    def clean_key(self, key: str) -> str:
        return re.sub(r"[^a-z0-9]", "", key.lower())

    def normalize_value(self, value: object, definition: FieldDefinition) -> str:
        normalized = re.sub(r"\s+", " ", str(value)).strip()
        data_type = (definition.data_type or "").lower()
        if data_type in {"numeric", "integer", "real"}:
            normalized = normalized.replace(",", "")
        return normalized


@lru_cache(maxsize=1)
def get_field_dictionary() -> FieldDictionary:
    return FieldDictionary()
