import pytest
from pydantic import ValidationError

from narration.knowledge import (
    InMemoryKnowledgeStore,
    KnowledgeDraft,
    LocationContext,
    PlaceAlias,
    PlaceCandidate,
    ResolutionStatus,
    Scope,
    Source,
)
from narration.knowledge.normalization import normalized_name


def _source(provider: str, slug: str, evidence_text: str = "") -> Source:
    return Source.from_url(
        provider=provider,
        title=slug,
        url=f"https://example.org/{slug}",
        evidence_text=evidence_text,
    )


def _candidate(source: Source, name: str, **kwargs) -> PlaceCandidate:
    if "lat" in kwargs and "lon" in kwargs:
        kwargs.setdefault("coordinate_source", "test:known-place")
    return PlaceCandidate(name=name, city="Wrocław", source_ids=[source.source_id], **kwargs)


def test_models_validate_coordinates_scope_and_source_identity():
    assert LocationContext(lat=51.12, lon=17.03, region="Dolny Śląsk").region == "Dolny Śląsk"
    assert Scope("DISTRICT") is Scope.DISTRICT
    assert _source("tavily", "bridge").source_id != _source("ddgs", "bridge").source_id
    assert (
        Source.from_url(provider="ddgs", title="A", url="https://EXAMPLE.org/bridge#section").source_id
        == Source.from_url(provider="ddgs", title="A", url="https://example.org/bridge").source_id
    )
    with pytest.raises(ValidationError):
        PlaceCandidate(name="Most", city="Wrocław", source_ids=["x"], lat=51.12)
    with pytest.raises(ValidationError, match="coordinate_source"):
        PlaceCandidate(name="Most", city="Wrocław", source_ids=["x"],
                       lat=51.12, lon=17.03)
    with pytest.raises(ValidationError):
        KnowledgeDraft(scope=Scope.DISTRICT, anchor_name="Nadodrze", city="Wrocław",
                       topic="history", content="Fakt.", source_ids=["x"],
                       source_worker="wikimedia", lat=51.12, lon=17.03)
    with pytest.raises(ValidationError):
        LocationContext(lat=91, lon=17)
    with pytest.raises(ValidationError):
        Source(source_id="src_001", provider="ddgs", title="Bridge", url="https://example.org/bridge")
    assert normalized_name("Łódź") == "lodz"
    assert normalized_name("Αθήνα") != normalized_name("Москва")


def test_verified_alias_and_nearby_coordinates_resolve_to_one_place():
    store = InMemoryKnowledgeStore()
    tavily = store.add_source(_source("tavily", "grunwaldzki"))
    ddgs = store.add_source(_source(
        "ddgs", "kaiserbruecke", "Most Grunwaldzki był nazywany Kaiserbrücke."
    ))
    first = store.resolve_place(
        _candidate(tavily, "Most Grunwaldzki", lat=51.1094, lon=17.0605)
    )
    second = store.resolve_place(
        _candidate(
            ddgs,
            "Kaiserbrücke",
            lat=51.10945,
            lon=17.06055,
            aliases=[PlaceAlias(name="Most Grunwaldzki", source_id=ddgs.source_id)],
        )
    )

    assert first.status is ResolutionStatus.CREATED
    assert second.status is ResolutionStatus.MATCHED
    assert second.reason == "name_or_alias_and_coordinates"
    assert second.place.place_id == first.place.place_id
    assert second.place.canonical_name == "Most Grunwaldzki"
    assert {alias.name for alias in second.place.aliases} == {"Kaiserbrücke"}
    assert len(store.places) == 1


def test_proximity_without_name_evidence_does_not_merge():
    store = InMemoryKnowledgeStore()
    source = store.add_source(_source("wikimedia", "nearby"))
    store.resolve_place(_candidate(source, "Most Grunwaldzki", lat=51.1094, lon=17.0605))
    second = store.resolve_place(
        _candidate(source, "Budynek obok mostu", lat=51.10945, lon=17.06055)
    )

    assert second.status is ResolutionStatus.CREATED_UNCERTAIN
    assert second.possible_match_ids
    assert len(store.places) == 2


def test_same_name_at_distant_coordinates_creates_two_places():
    store = InMemoryKnowledgeStore()
    source = store.add_source(_source("tavily", "same-name"))
    first = store.resolve_place(
        _candidate(source, "Pomnik Wolności", lat=51.12, lon=17.03)
    )
    second = store.resolve_place(
        _candidate(source, "Pomnik Wolności", lat=51.20, lon=17.10)
    )
    assert first.place.place_id != second.place.place_id
    assert second.status is ResolutionStatus.CREATED


def test_same_name_without_sufficient_location_evidence_stays_separate():
    store = InMemoryKnowledgeStore()
    source = store.add_source(_source("ddgs", "ambiguous"))
    first = store.resolve_place(_candidate(source, "Kościół św. Jadwigi"))
    second = store.resolve_place(_candidate(source, "Kosciol sw Jadwigi"))

    assert second.status is ResolutionStatus.CREATED_UNCERTAIN
    assert second.possible_match_ids == [first.place.place_id]
    assert len(store.places) == 2


def test_same_name_and_street_match_without_coordinates():
    store = InMemoryKnowledgeStore()
    source = store.add_source(_source("ddgs", "street"))
    first = store.resolve_place(_candidate(source, "Dom pod Słońcem", street="ul. Różana"))
    second = store.resolve_place(_candidate(source, "Dom pod Sloncem", street="Różana"))
    assert second.status is ResolutionStatus.MATCHED
    assert second.place.place_id == first.place.place_id


def test_conflicting_external_ids_do_not_merge():
    store = InMemoryKnowledgeStore()
    source = store.add_source(_source("wikimedia", "ids"))
    store.resolve_place(
        _candidate(source, "Most Grunwaldzki", lat=51.1094, lon=17.0605,
                   external_ids={"wikidata": "Q1"})
    )
    second = store.resolve_place(
        _candidate(source, "Most Grunwaldzki", lat=51.1094, lon=17.0605,
                   external_ids={"wikidata": "Q2"})
    )
    assert second.status is ResolutionStatus.CREATED
    assert len(store.places) == 2


def test_matching_external_id_resolves_historical_name_without_alias():
    store = InMemoryKnowledgeStore()
    first_source = store.add_source(_source("wikimedia", "id-first"))
    second_source = store.add_source(_source("tavily", "id-second"))
    first = store.resolve_place(
        _candidate(first_source, "Most Grunwaldzki", external_ids={"wikidata": "Q123"})
    )
    second = store.resolve_place(
        _candidate(second_source, "Kaiserbrücke", external_ids={"wikidata": "Q123"})
    )
    assert second.status is ResolutionStatus.MATCHED
    assert second.reason == "matching_external_id"
    assert second.place.place_id == first.place.place_id


def test_later_coordinates_enrich_place_referenced_by_existing_chunk():
    store = InMemoryKnowledgeStore()
    source = store.add_source(_source("wikimedia", "coordinates"))
    first = store.resolve_place(_candidate(source, "Dom pod Słońcem", street="Różana"))
    chunk = store.add_chunk(
        KnowledgeDraft(scope=Scope.PLACE, place_id=first.place.place_id,
                       anchor_name="Dom pod Słońcem", topic="history",
                       content="Fakt testowy.", source_ids=[source.source_id],
                       source_worker="wikimedia")
    )
    assert "lat" not in chunk.model_fields_set
    store.resolve_place(
        _candidate(source, "Dom pod Słońcem", street="ul. Różana", lat=51.12, lon=17.03)
    )
    assert store.places[0].lat == 51.12
    assert store.places[0].lon == 17.03
    assert store.places[0].coordinate_source == "test:known-place"
    assert store.chunks[0].place_id == first.place.place_id
    assert "lat" not in store.chunks[0].model_dump()


def test_alias_must_cite_registered_candidate_source():
    store = InMemoryKnowledgeStore()
    source = store.add_source(_source("ddgs", "registered"))
    with pytest.raises(ValueError, match="alias source"):
        store.resolve_place(
            _candidate(source, "Kaiserbrücke", aliases=[PlaceAlias(name="Most Grunwaldzki", source_id="other")])
        )


def test_store_does_not_require_alias_literal_in_one_source_excerpt():
    store = InMemoryKnowledgeStore()
    source = store.add_source(_source("ddgs", "unsupported"))
    place = store.resolve_place(
        _candidate(source, "Kaiserbrücke", aliases=[
            PlaceAlias(name="Most Grunwaldzki", source_id=source.source_id)
        ])
    ).place
    assert [alias.name for alias in place.aliases] == ["Most Grunwaldzki"]


def test_alias_can_be_cited_when_canonical_name_is_inferred_from_document():
    store = InMemoryKnowledgeStore()
    source = store.add_source(_source(
        "tavily", "historical-bridge",
        "Kaiserbrücke została odbudowana po wojnie.",
    ))
    place = store.resolve_place(_candidate(
        source, "Most Grunwaldzki",
        aliases=[PlaceAlias(name="Kaiserbrücke", source_id=source.source_id)],
    )).place
    assert [alias.name for alias in place.aliases] == ["Kaiserbrücke"]


def test_chunk_rejects_unknown_source_and_deduplicates_cross_worker_fact():
    store = InMemoryKnowledgeStore()
    tavily = store.add_source(_source("tavily", "bridge"))
    ddgs = store.add_source(_source("ddgs", "bridge"))
    place = store.resolve_place(_candidate(tavily, "Most Grunwaldzki", lat=51.1094, lon=17.0605)).place

    with pytest.raises(ValueError, match="unknown source_ids"):
        store.add_chunk(KnowledgeDraft(scope=Scope.PLACE, place_id=place.place_id,
                                       anchor_name=place.canonical_name, topic="history",
                                       content="Zweryfikowany fakt.", source_ids=["unknown"],
                                       source_worker="tavily"))

    first = store.add_chunk(
        KnowledgeDraft(scope=Scope.PLACE, place_id=place.place_id,
                       anchor_name=place.canonical_name, topic="history",
                       content="Zweryfikowany fakt.", source_ids=[tavily.source_id],
                       source_worker="tavily")
    )
    second = store.add_chunk(
        KnowledgeDraft(scope=Scope.PLACE, place_id=place.place_id,
                       anchor_name="Kaiserbrücke", topic="history",
                       content="Zweryfikowany fakt.", source_ids=[ddgs.source_id],
                       source_worker="ddgs")
    )
    assert second.chunk_id == first.chunk_id
    assert second.source_ids == sorted([tavily.source_id, ddgs.source_id])
    assert second.source_workers == ["ddgs", "tavily"]
    assert store.places[0].lat == 51.1094
    assert "lat" not in second.model_dump()
    assert len(store.chunks) == 1


def test_district_chunk_is_shared_by_name_and_city_without_coordinates():
    store = InMemoryKnowledgeStore()
    source = store.add_source(_source("wikimedia", "nadodrze"))
    draft = KnowledgeDraft(scope=Scope.DISTRICT, anchor_name="Nadodrze", city="Wrocław",
                           topic="history", content="Fakt o dzielnicy.",
                           source_ids=[source.source_id], source_worker="wikimedia")
    first = store.add_chunk(draft)
    second = store.add_chunk(draft)
    assert first.chunk_id == second.chunk_id
    assert first.place_id is None
    assert first.city == "Wrocław"
    assert "lat" not in first.model_dump()
    assert len(store.chunks) == 1


def test_place_chunk_city_comes_from_resolved_place():
    store = InMemoryKnowledgeStore()
    source = store.add_source(_source("tavily", "place-city"))
    place = store.resolve_place(_candidate(source, "Most Testowy")).place
    draft = KnowledgeDraft(scope=Scope.PLACE, place_id=place.place_id,
                           anchor_name=place.canonical_name, topic="history",
                           content="Fakt o miejscu.", source_ids=[source.source_id],
                           source_worker="tavily")
    assert store.add_chunk(draft).city == "Wrocław"
    with pytest.raises(ValueError, match="city conflicts"):
        store.add_chunk(draft.model_copy(update={"city": "Kraków"}))


def test_place_chunk_requires_resolved_place():
    store = InMemoryKnowledgeStore()
    source = store.add_source(_source("wikimedia", "district"))
    with pytest.raises(ValueError, match="requires a resolved place_id"):
        store.add_chunk(KnowledgeDraft(scope=Scope.PLACE, anchor_name="Most",
                                       topic="history", content="Fakt.",
                                       source_ids=[source.source_id], source_worker="wikimedia"))


def test_store_returns_copies_not_mutable_internal_objects():
    store = InMemoryKnowledgeStore()
    source = store.add_source(_source("ddgs", "copy"))
    place = store.resolve_place(_candidate(source, "Dom", street="Różana")).place
    place.canonical_name = "Mutated"
    assert store.places[0].canonical_name == "Dom"
