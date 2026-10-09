# AI service

Serwis AI odbiera lokalizacje z Redis Stream, uruchamia pipeline narracyjny i publikuje listę POI oraz opcjonalną narrację na kanale przypisanym do sesji.

## Przepływ danych

```text
Backend
  -> Redis Stream: location:events
  -> RedisStreamWorker
  -> NarrationEventHandler
  -> TourNarrationPipeline
  -> Redis Pub/Sub: tour:{session_id}
```

Worker publikuje:

- komunikat `pois` z wybranymi punktami zainteresowania,
- komunikat `narration` z wygenerowanym tekstem, jeżeli event wymaga narracji.

Oba komunikaty dla jednego wyniku otrzymują wspólne `narration_id`.

## Struktura kodu

```text
AI/
├── main.py                 # punkt wejścia
├── bootstrap.py            # tworzenie i łączenie zależności
├── app_config.py           # ustawienia całej aplikacji
├── narration/              # kompletny pipeline narracyjny
├── workers/                # odbiór i publikowanie zdarzeń
├── integrations/           # adaptery zewnętrznych usług
├── photos/                 # wybór i zapis obrazów POI
└── shared/                 # małe współdzielone mechanizmy
```

### `narration/`

```text
narration/
├── pipeline.py             # kolejność wykonywania kroków i default()
├── steps.py                # kontrakty kroków pipeline'u
├── config/                 # globalne ustawienia narracji
├── schemas/                # modele wejścia i wyników pipeline'u
├── location_discovery/     # adres i pobliskie POI
├── poi_selection/          # ranking i wybór POI
├── poi_enrichment/         # dodatkowe informacje o POI
├── information_filtering/  # przygotowanie kontekstu
└── narration_generation/   # prompt, model i parser narracji
```

`TourNarrationPipeline` jest bezstanowy. Tworzy się go raz, a dane konkretnego zdarzenia przekazuje przez `NarrationPipelineRequest`:

```python
request = NarrationPipelineRequest(
    session_id=session_id,
    settings=narration_settings,
)

result = pipeline.run(request)
```

`pipeline.py` zna kontrakty z `steps.py`, a implementacje znajdują się w katalogach poszczególnych kroków. Kontrakty zewnętrznych dostawców są umieszczone przy krokach, które ich potrzebują.

### `workers/`

`workers/redis_narration/redis_stream_worker.py` obsługuje wyłącznie transport Redis: odczyt streamu, preferencje, publikację i kursor.

`NarrationEventHandler` obsługuje pojedynczy event, mapuje go na `NarrationPipelineRequest`, uruchamia pipeline i buduje wiadomości dla backendu.

### `integrations/`

Integracje implementują kontrakty z modułu narracyjnego:

```text
GeocodingClient       -> NominatimClient
PoiDataClient         -> OverpassClient
SearchClient          -> WikimediaSearchClient / DuckDuckGoSearchClient
LanguageModel         -> NvidiaLanguageModel / OllamaLanguageModel
SeenPoiRepository     -> RedisSeenPoiRepository
ImageStorage          -> MinioImageStorage
```

Pipeline nie importuje konkretnych integracji. Wszystkie implementacje są łączone w `bootstrap.py`.

## Kroki pipeline'u

1. `LocationDiscoveryTask` pobiera adres z Nominatim i pobliskie POI z Overpass.
2. `PoiSelectionTask` ocenia kandydatów na podstawie odległości, kategorii i sygnałów popularności.
3. `PoiEnrichmentTask` pobiera kontekst z Wikimedia; w przypadku błędu tworzy ostrożny fallback z danych OSM.
4. `InformationFilteringTask` przygotowuje kontekst zgodny z preferencjami użytkownika.
5. `NarrationGenerationTask` buduje prompt, wywołuje model językowy i parsuje odpowiedź.

Gdy `include_narration=false`, pipeline działa w trybie planowania: wybiera kilka POI i pomija enrichment oraz generowanie narracji.

## Uruchomienie w trybie mock

Tryb mock nie wymaga klucza NVIDIA ani usług geocodingowych.

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Domyślna wartość to:

```dotenv
AI_MOCK=true
```

## Uruchomienie live

W `.env` ustaw:

```dotenv
AI_MOCK=false
NVIDIA_API_KEY=...
NOMINATIM_USER_AGENT=AI-Tour-Guide/0.1 (contact: your-email@example.com)
WIKIMEDIA_USER_AGENT=AI-Tour-Guide/0.1 (contact: your-email@example.com)
```

Następnie:

```powershell
docker compose up --build
```

Domyślny live pipeline korzysta z NVIDIA. Adapter Ollama pozostaje dostępny, ale nie jest podłączony przez `TourNarrationPipeline.default()`.

## Konfiguracja

Konfiguracja jest przechowywana przy komponencie, którego dotyczy:

- `narration/config/` — globalne ustawienia narracji,
- `narration/poi_selection/config/` — scoring oraz pamięć zobaczonych POI,
- `narration/information_filtering/config/` — budowanie kontekstu,
- `integrations/**/config/` — timeouty, modele i endpointy integracji,
- `workers/redis_narration/config/` — ustawienia workera Redis,
- `photos/config/` — mapowanie kategorii POI na obrazy.

Konfiguracje integracji korzystają z `pydantic-settings` i zmiennych środowiskowych. Implementacje kroków otrzymują gotowe obiekty konfiguracyjne przez konstruktory.

## Testy

W aktywnym środowisku Python z zależnościami projektu:

```powershell
cd AI
$env:PYTHONPATH = (Get-Location).Path
python -m pytest tests -q
```

Testy są ułożone zgodnie z modułami produkcyjnymi: pipeline, kroki, worker, mappery i integracje są testowane oddzielnie.

## Ręczny test Redisa

Subskrypcja wyniku:

```powershell
docker compose exec redis redis-cli SUBSCRIBE tour:test-session-1
```

Wysłanie lokalizacji:

```powershell
docker compose exec redis redis-cli XADD location:events "*" session_id test-session-1 lat 52.2297 lng 21.0122
```

Oczekiwane komunikaty:

```json
{"type":"pois","data":[]}
{"type":"narration","text":"..."}
```

## Uwagi operacyjne

- Publiczne serwery Overpass mogą zwracać HTTP 429 lub timeouty; klient obsługuje rotację serwerów i retry.
- Wikimedia wymaga poprawnego `User-Agent`.
- DuckDuckGo i Ollama są zachowane jako alternatywne adaptery, ale nie są częścią domyślnego pipeline'u.
- Zdjęcia są obecnie statycznymi obrazami przypisanymi do kategorii POI i przechowywanymi w MinIO.
