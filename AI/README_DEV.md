# TourGuide AI

Obecny prototyp zbiera informacje o miejscach do wspólnego magazynu wiedzy. Kod wykonawczy jest w `narration/` i `integrations/`; notebook [tourguide_pipeline_prototype.ipynb](experiments/tourguide_pipeline_prototype.ipynb) uruchamia go i pokazuje wyniki.

## Obecny przepływ

```text
GPS -> Nominatim -> LocationContext
                    ├── WikimediaWorker -> źródła i chunki obszarowe
                    └── TavilyResearchWorker -> ranking -> ekstrakcje -> jeden wsad LLM
                                                              -> model + narzędzia geokodowania PLACE
                                                     -> Place i chunki PLACE
```

- `narration/location_discovery/` tworzy kontekst lokalizacji po reverse geocodingu.
- `narration/research/` zawiera workery Wikimedia i Tavily oraz kontrakty klientów.
- `narration/knowledge/` zawiera modele, rozstrzyganie tożsamości miejsca i wspólny magazyn w pamięci.
- `integrations/` zawiera używane adaptery Nominatim, Wikimedia, Tavily i NVIDIA.
- `workers/redis_narration/` zachowuje transport Redis i mapowanie komunikatów backendu. Tryb mock jest dostępny; nowy pipeline live nie jest jeszcze podłączony do workera.
- `photos/` i MinIO pozostają przy transporcie oraz demonstracyjnym trybie mock.

`Place` przechowuje punkt reprezentacyjny oraz wszystkie pasujące wyniki geokodowania w `locations`, każdy ze źródłem i identyfikatorem. Chunki `PLACE` odwołują się do `place_id`; chunki obszarowe pozostają przypisane nazwą i miastem.

Notebook używa teraz dwóch narzędzi dla modelu: `geocode_address(address, city, country)` zwraca potwierdzone punkty adresowe GUS, a `search_place(name, aliases, city, country)` łączy kandydatów z Wikipedii, Overture Places i Nominatim. Wyniki zachowują nazwę, typ, współrzędne, źródło i własny `candidate_id`. Model wybiera identyfikatory, a kod przyjmuje tylko punkty rzeczywiście zwrócone przez narzędzia oraz zgodne z miastem i krajem. Kilka wybranych punktów trafia do jednego `Place.locations`. Krótki zakres numerów z tekstu źródłowego, np. 14-16, może dać kilka punktów adresowych. Pusta lista wyników jest odróżniana od błędu usługi.

Notebook ma osobne `RESEARCH_MODEL_NAME` i `GEOCODING_MODEL_NAME` w pierwszej komórce. Domyślne ustawienia modelu geokodowania są w `narration/research/config/geocoding_model_config.py`, a limity wywołań narzędzi i liczby punktów w `narration/knowledge/place_location_config.py`.

Na końcu notebooka jest osobny eksperyment `UnifiedTavilyGlmExperiment`. Korzysta z tekstów już zebranych przez Tavily i przekazuje je w pierwszym żądaniu do GLM wraz z dwoma narzędziami geokodowania. Model może zażądać wyszukania wielu miejsc w jednej odpowiedzi, a po otrzymaniu wyników zwraca pełne chunki oraz identyfikatory wybranych punktów. Wynik trafia do oddzielnego store, więc można go porównać z obecnym przebiegiem bez mieszania danych. Pomiar eksperymentu obejmuje GLM i geokodery; nie obejmuje ponownie wyszukiwania i ekstrakcji Tavily. Limity eksperymentu są w `narration/research/config/unified_research_config.py`.
Krótka próba live tool calling na GLM przez NVIDIA API zakończyła się timeoutem po 180 s; kolejna z `clear_thinking=true` po 60 s. Obsługa narzędzi jest zadeklarowana przez dostawcę, ale wydajność tego wariantu pozostaje niepotwierdzona.

Poprzedni `PlaceLocationResolver` pozostaje dostępny jako alternatywny tryb workera. W nim Nominatim wymaga zgodności nazwy, miasta i kraju; spośród zgodnych punktów reprezentant jest wybierany według nazwy, a następnie odległości.

Worker Tavily zbiera do dwóch udanych ekstrakcji w maksymalnie czterech próbach, łączy ich tekst i wywołuje model raz. Model tworzy samodzielne, parafrazowane chunki dla rozpoznanych miejsc i obszarów. Dosłowny cytat nie jest wymagany. Każdy chunk ma `source_ids` i `source_urls` wszystkich stron użytych we wsadzie; są to URL-e wejściowe, nie indywidualne potwierdzenie każdego faktu. Każde źródło zachowuje swój tekst wejściowy w `evidence_text` do diagnostyki. Miejsca poza bieżącą okolicą mogą trafić do store; chunk PLACE wymaga współrzędnych pasujących do nazwy i miasta.

Model ekstrakcji zwraca też opcjonalne `address` dla każdego PLACE. PLACE bez miasta wskazanego przez model nie jest geokodowany na podstawie miasta bieżącego GPS. W trybie narzędziowym model może wywołać geokodowanie kilku adresów wskazanych w opisie miejsca. Punkt GUS ma `location_type="address"`, aby nie mylić adresu z tożsamością całego obiektu. Overture czyta dane tylko z obszaru wokół badanego GPS i pomija miejsca z innego miasta; dla nich pozostaje globalne wyszukiwanie Nominatim. Pierwsze zapytanie Overture pobiera wycinek danych i może potrwać dłużej. `overturemaps` jest zależnością z `requirements.txt`.

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
