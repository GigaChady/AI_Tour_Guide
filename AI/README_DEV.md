# TourGuide AI

Obecny prototyp zbiera informacje o miejscach do wspólnego magazynu wiedzy. Kod wykonawczy jest w `narration/` i `integrations/`; notebook [tourguide_pipeline_prototype.ipynb](experiments/tourguide_pipeline_prototype.ipynb) uruchamia go i pokazuje wyniki.

## Obecny przepływ

```text
GPS -> Nominatim -> LocationContext
                    ├── WikimediaWorker -> źródła i chunki obszarowe
                    └── TavilyResearchWorker -> ranking -> ekstrakcje -> jeden wsad LLM
                                                              -> geokodowanie PLACE
                                                     -> Place i chunki PLACE
```

- `narration/location_discovery/` tworzy kontekst lokalizacji po reverse geocodingu.
- `narration/research/` zawiera workery Wikimedia i Tavily oraz kontrakty klientów.
- `narration/knowledge/` zawiera modele, rozstrzyganie tożsamości miejsca i wspólny magazyn w pamięci.
- `integrations/` zawiera używane adaptery Nominatim, Wikimedia, Tavily i NVIDIA.
- `workers/redis_narration/` zachowuje transport Redis i mapowanie komunikatów backendu. Tryb mock jest dostępny; nowy pipeline live nie jest jeszcze podłączony do workera.
- `photos/` i MinIO pozostają przy transporcie oraz demonstracyjnym trybie mock.

`Place` przechowuje punkt reprezentacyjny oraz wszystkie pasujące wyniki geokodowania w `locations`, każdy ze źródłem i identyfikatorem. Chunki `PLACE` odwołują się do `place_id`; chunki obszarowe pozostają przypisane nazwą i miastem.

Przy geokodowaniu przez Nominatim wymagamy zgodności nazwy miejsca i miasta oraz, gdy kraj jest podany przez wynik, kraju. Ulica jest zachowywana jako metadana, lecz nie odrzuca wyniku. Spośród zgodnych punktów wybierany jest reprezentant z najlepszą zgodnością nazwy, a następnie najbliższy pozycji badawczej; wszystkie zgodne punkty pozostają w `locations`.

Worker Tavily zbiera do dwóch udanych ekstrakcji w maksymalnie czterech próbach, łączy ich tekst i wywołuje model raz. Model tworzy samodzielne, parafrazowane chunki dla rozpoznanych miejsc i obszarów. Dosłowny cytat nie jest wymagany. Każdy chunk ma `source_ids` i `source_urls` wszystkich stron użytych we wsadzie; są to URL-e wejściowe, nie indywidualne potwierdzenie każdego faktu. Każde źródło zachowuje swój tekst wejściowy w `evidence_text` do diagnostyki. Miejsca poza bieżącą okolicą mogą trafić do store; chunk PLACE wymaga współrzędnych pasujących do nazwy i miasta.

Wyszukiwanie Tavily zbiera wyniki zapytań o osiedle, ulicę i miasto, deduplikuje URL-e i porządkuje je na podstawie tytułu oraz opisu wyniku. Wzmianki o bieżącej lokalizacji zwiększają priorytet, ale nie blokują zapisania odległego miejsca. Pusta ekstrakcja nie trafia do wsadu; worker próbuje kolejną stronę z rankingu. Przy braku współrzędnych diagnostyka podaje liczbę wyników Nominatim i reguły, które je odrzuciły.

Adapter Tavily przed zastosowaniem limitu znaków usuwa wiersze złożone wyłącznie z linków Markdown oraz zamienia linki w zwykłych zdaniach na ich etykiety. Nie usuwa zwykłego tekstu menu ani komunikatów cookies bez składni linku; notebook pokazuje surowy i oczyszczony fragment, aby ocenić potrzebę dalszych reguł.

Limity wyszukiwania, prób ekstrakcji, długości tekstu, liczby i długości chunków oraz wagi rankingu są w `narration/research/config/web_research_config.py`. Reguły dla modelu są w `narration/research/config/web_research_prompt.py`, parametry wywołania modelu w `research_model_config.py`, a limity klienta Tavily w `integrations/knowledge/tavily/config/tavily_config.py`.

## Uruchomienie prototypu

Zainstaluj zależności z `requirements.txt`, otwórz notebook i wpisz klucze w pierwszej komórce. Uruchom komórki od początku po zmianach kodu. Notebook korzysta z usług zewnętrznych i obecnie zapisuje dane wyłącznie w pamięci kernela.

## Testy

W środowisku Pythona z zależnościami projektu, z katalogu repozytorium:

```powershell
$env:PYTHONPATH = (Resolve-Path AI).Path
python -m pytest AI/tests -q
```

## Transport Redis/Docker

`main.py` i `bootstrap.py` zachowują punkt wejścia workera Redis dla trybu mock. Przy `AI_MOCK=false` start zgłasza czytelny błąd, dopóki nowy pipeline nie zostanie połączony z transportem. Obrazy w `photos/` oraz adapter MinIO pozostały dla tego trybu. Stary pipeline oparty na Overpass, selekcji POI i bezpośrednim generowaniu narracji został usunięty.
