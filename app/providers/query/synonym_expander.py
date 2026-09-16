from dataclasses import dataclass


@dataclass(slots=True)
class SynonymExpandResult:
    search_query: str
    synonym_expansions: list[str]
    synonym_applied: bool


def _term_matches(query: str, term: str) -> bool:
    if not term:
        return False
    if term.isascii():
        return term.lower() in query.lower()
    return term in query


def expand_synonyms(effective_query: str, settings: dict | None) -> SynonymExpandResult:
    if not effective_query:
        return SynonymExpandResult(
            search_query=effective_query,
            synonym_expansions=[],
            synonym_applied=False,
        )

    synonyms = (settings or {}).get("synonyms") or []
    if not isinstance(synonyms, list) or not synonyms:
        return SynonymExpandResult(
            search_query=effective_query,
            synonym_expansions=[],
            synonym_applied=False,
        )

    expansions: list[str] = []
    for group in synonyms:
        if not isinstance(group, dict):
            continue
        terms = group.get("terms") or []
        expand_words = group.get("expand") or []
        if not isinstance(terms, list) or not isinstance(expand_words, list):
            continue
        if not any(
            _term_matches(effective_query, term)
            for term in terms
            if isinstance(term, str)
        ):
            continue
        for word in expand_words:
            if isinstance(word, str) and word and word not in expansions:
                expansions.append(word)

    if not expansions:
        return SynonymExpandResult(
            search_query=effective_query,
            synonym_expansions=[],
            synonym_applied=False,
        )

    search_query = f"{effective_query} {' '.join(expansions)}"
    return SynonymExpandResult(
        search_query=search_query,
        synonym_expansions=expansions,
        synonym_applied=True,
    )
