import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path


AMBIGUOUS_HEADERS = {"REF", "REFERENCE", "ID", "NO", "NUMBER", "DATE", "AMOUNT"}
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "aliases.json"


def normalize_header(value: str) -> str:
    normalized = re.sub(r"[^A-Z0-9]+", "_", str(value).strip().upper())
    return re.sub(r"_+", "_", normalized).strip("_")


@dataclass(frozen=True)
class MappingProposal:
    source_column: str
    canonical_field: str | None
    confidence: float
    mapping_method: str


class MappingService:
    def __init__(self, aliases_path: Path = CONFIG_PATH) -> None:
        with aliases_path.open(encoding="utf-8") as handle:
            configured: dict[str, list[str]] = json.load(handle)
        self.aliases = {
            field: {normalize_header(alias) for alias in aliases + [field]}
            for field, aliases in configured.items()
        }
        self.alias_to_field = {
            alias: field for field, aliases in self.aliases.items() for alias in aliases
        }

    @property
    def canonical_fields(self) -> list[str]:
        return list(self.aliases)

    def propose(
        self, source_column: str, learned_mappings: dict[str, str] | None = None
    ) -> MappingProposal:
        normalized = normalize_header(source_column)
        learned_mappings = learned_mappings or {}

        if normalized in learned_mappings:
            return MappingProposal(source_column, learned_mappings[normalized], 1.0, "company_confirmed")
        if normalized in AMBIGUOUS_HEADERS:
            return MappingProposal(source_column, None, 0.0, "unresolved_ambiguous")
        if normalized in self.alias_to_field:
            return MappingProposal(source_column, self.alias_to_field[normalized], 0.99, "known_alias")

        scored = sorted(
            (
                SequenceMatcher(None, normalized, alias).ratio(),
                field,
            )
            for field, aliases in self.aliases.items()
            for alias in aliases
        )
        best_score, best_field = scored[-1]
        second_score = scored[-2][0] if len(scored) > 1 else 0.0
        if best_score >= 0.86 and best_score - second_score >= 0.08:
            return MappingProposal(source_column, best_field, round(best_score, 2), "fuzzy")
        return MappingProposal(
            source_column,
            None,
            round(best_score, 2) if best_score >= 0.5 else 0.0,
            "unresolved",
        )

