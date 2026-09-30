# Plan: Save and reports for every model

Goal: every calculator in the sidebar can be saved to "Projetos salvos", opened as a
printable report and re-run with its original inputs. Phases 0–6 cover **Opções
Financeiras**; Phase 7 extends the same mechanism to the other modules.

**Status:** Phases 0–6 are implemented (Phase 4 was first dropped, then done). What is
left: the manual check in §5 and Phase 7 (the other modules). §6 lists what was
deliberately left out.

---

## 1. State

| Screen | Template | Save | Report | Rerun |
| --- | --- | :-: | :-: | :-: |
| Black-Scholes | `financeiros/black-sholes.html` | ✅ | ✅ | ✅ |
| Black-Scholes-Merton | `financeiros/black-scholes-merton.html` | ✅ | ✅ | ✅ |
| Generalized BSM | `financeiros/generalized-black-scholes-merton.html` | ✅ | ✅ | ✅ |
| Cox-Ross-Rubinstein | `financeiros/cox-ross-rubinstein.html` | ✅ | ✅ | ✅ |
| Monte Carlo European | `financeiros/options_price_mcs.html` | ✅ | ✅ | ✅ |
| Monte Carlo American | `financeiros/options_price_american_mcs.html` | ✅ | ✅ | ✅ |
| FDM European | `financeiros/fdm_european.html` | ✅ | ✅ | ✅ |
| Call & Put payoff | `financeiros/call_put_options.html` | ✅ | ✅ | ✅ |
| Asset + Put | `financeiros/asset_put_combination.html` | ✅ | ✅ | ✅ |
| Bull / Bear spread | `financeiros/bull_bear_spread.html` | ✅ | ✅ | ✅ |
| Collar | `financeiros/collar_option.html` | ✅ | ✅ | ✅ |
| Return & volatility | `teoria/volatilidade.html` (app `teoria_opcao`) | ✅ | ✅ | ✅ |

Before this plan, FDM European, the four strategy screens and Return & volatility had
no save, report or rerun, and the CRR report had bug 1. The screens of the other
modules are listed in Phase 7.

**Out of scope:** the `to_do` placeholder cards in `cox_ross_overview.html`,
`finite_difference_overview.html` (American FDM) and `monte_carlo_overview.html`.
These models don't exist yet. When someone builds them, they follow the recipe in §7.

### 1.1 How saving and reports worked before this plan

- **Front end:** each template had its own copy of `saveProject()`, about 60 lines. It
  read the parameters from the inputs and the results from the DOM (`textContent`,
  `img.src`, `innerHTML`) when Save was clicked, then POSTed JSON.
- **Save:** two near-identical views, `save_black_schole_model_view` and
  `save_mcs_model`. Both set `report='online'`, a string sentinel in the `FileField`.
  Its only job is to make `{% if simulation.report %}` show "Ver Relatório".
- **Report:** `view_report_view` built its context with an `if/elif` on `model_type`
  and rendered `report/report_template.html`. The result is an HTML page that the user
  prints with `window.print()`. Nothing calls the WeasyPrint helpers in
  `use_cases/generate_save_pdf.py`; they are dead code. (This also means §1 of
  `PLANO_MARKOWITZ.md` is wrong where it says the reports are made with WeasyPrint.)
- **Rerun:** `rerun_simulation_view` was another `if/elif` that mapped `model_type` to
  a template.
- **List:** `simulation_list.html` had a hard-coded `or` chain of the types that could
  be re-run.

Adding **one** model meant editing five places: the choices, the tuple in the save
view, the report `if/elif`, the rerun `if/elif` and the list template. Phase 1
replaced all of them with a single registry.

### 1.2 Bugs found while reading the code (all fixed)

1. **The CRR report left "Down factor" blank.** The report read `results['d2']`, but the
   CRR payload stores the value as `downFactor`.
2. **The save endpoints had no `@login_required`.** An anonymous POST got a 500
   instead of a redirect.
3. **The report title was always in Portuguese** (`"Relatório - …"`), even when the
   session language is `en`.
4. **The FDM grid labels were swapped.** `grid_m` holds `M_time` (the time steps), but
   the screen showed it as "Price Steps (M)"; `grid_n` (space steps) was labelled
   "Time Steps (N)".
5. **The limit was off by one.** `clean()` checked `current_count >= 41`, which allows
   41 records, while the error message says 40.
6. **Model validation never ran** (found during implementation). `save()` and `clean()`
   tested `self.pk is None`, but `id` is a UUID with a default, so `pk` is never
   `None`. `full_clean()` was never called: neither the 40-model limit nor the
   `model_type` choices were enforced. Both now test `self._state.adding`, and
   `save()` calls `full_clean(exclude=['report'])`, because the `'online'` sentinel
   would fail the field's `.pdf` extension validator.
   **Consequence:** the limit is enforced for the first time. A user who already has
   more than 40 saves can't save again until they delete some.

---

## 2. Design (as built)

### 2.1 Registry: `financial_options/report_registry.py`

One entry per `model_type`. The save, report, rerun, list and first-load code all read
from it.

```python
@dataclass(frozen=True)
class ModelSpec:
    template: str                                     # screen to re-run on
    build_report: Callable[[dict, dict, str], dict]   # (parameters, results, language) -> context
    defaults: dict = field(default_factory=dict)      # initial_data for first load and rerun
    param_labels: dict = field(default_factory=dict)  # {'pt': {key: label}, 'en': {...}}
    value_labels: dict = field(default_factory=dict)  # {'pt': {key: {value: label}}, 'en': {...}}
    table_params: tuple = ()                          # list inputs the report shows in a table instead

    def label_parameters(self, parameters, language): ...
```

`table_params` is for inputs that are a list (the price series of Return &
volatility): `label_parameters` leaves them out of the parameters section, and the
report builder shows them in its table.

`label_parameters` translates parameter names (`param_labels`) and choice values
(`value_labels`, e.g. `bullCall` → "Trava de Alta (c/ Call)"), and orders the
parameters as in `param_labels`. The ordering matters because PostgreSQL `jsonb`
does not keep key order.

How each consumer uses it:

| Consumer | Before | With the registry |
| --- | --- | --- |
| Save view | tuple of types that get `report='online'` | `if model_type in REGISTRY` |
| `view_report_view` | `if/elif` with six branches | `spec.label_parameters(...)` plus `spec.build_report(...)`; unknown type → 404 |
| `rerun_simulation_view` | `if/elif` with six branches | `spec.template`, `initial_data = {**spec.defaults, **params}` |
| `simulation_list.html` | `or` chain | `simulation.can_rerun` (model property, imported locally to avoid a cycle) |
| Screen GET views | `initial_data` dicts copied in each view | `_render_screen()` → `spec.defaults`, overridable from the query string |

The six existing report branches moved into `build_*_report` functions unchanged,
apart from the fix for bug 1. Merging `defaults` into the saved parameters also lets
old saves re-run after a screen gains a new input.

### 2.2 A single save endpoint

`save_financial_model` (`@login_required`, `@require_POST`) replaces the two old save
views. It saves once, with `report='online'` for every registry type. Invalid JSON
and missing fields return 400. A `ValidationError` from the model (an unknown
`model_type`, or the 40-model limit) also returns 400, which depends on the bug 6
fix. The `save-mcs-model/` route was removed in Phase 5, when the Monte Carlo
screens stopped posting to it.

### 2.3 Report template: generic tables

The strategy screens produce **a table with one row per price**. `report_template.html`
has a `tables` block after the `nested_results` section:

```django
{% for table in tables %}
  <h3>{{ table.title }}</h3>
  <table class="data-table">
    <thead><tr>{% for h in table.headers %}<th>{{ h }}</th>{% endfor %}</tr></thead>
    <tbody>
      {% for row in table.rows %}
        <tr>{% for cell in row %}<td>{{ cell }}</td>{% endfor %}</tr>
      {% endfor %}
    </tbody>
  </table>
{% endfor %}
```

`.data-table` has its own style: right-aligned cells, smaller padding, the header
repeated on each printed page, and page breaks allowed between rows. The results
table is hidden when a report has no summary values. Call & Put, Asset + Put and
Collar limit `divisions` to 5–50, so their tables fit on one or two A4 pages.
Bull/Bear does not (see §6).

### 2.4 Shared front-end helper: `static/app_teoria/home/save_project.js`

Loaded once in `home.html`. Screens are injected with `$('#main-content').html()`, so
the global function is available on every screen. All twelve screens use it.

```js
window.saetoSaveProject = function ({ button, url, modelType, parameters, results, lang }) {
  // spinner on the button, CSRF from the fragment's csrfmiddlewaretoken,
  // fetch, success and error alert in pt/en, restore the button
};
```

### 2.5 Saved HTML is sanitized before the report renders it

`interpretation` and the CRR `lattice` are built by the server, but the screen saves
them from the page (`innerHTML`), so what is stored is whatever the browser sent. The
report renders both with `|safe`, so `view_report_view` runs every key in
`REPORT_HTML_FIELDS` through `sanitize_report_html`
(`financial_options/report_html.py`) first.

It is an allowlist built on `html.parser`: it keeps the tags those two fragments use
(headings, `p`, `strong`, lists, `div`/`span`, tables, `hr`, `br`), keeps `class`,
`colspan` and `rowspan`, escapes all text, and drops everything else — scripts, event
handlers, `style`, links and images. Unbalanced tags are closed, so a truncated save
cannot swallow the rest of the report.

### 2.6 Rules for the screens

- **Take a snapshot when Calculate runs.** Store `lastRun = { parameters, results }`
  when a calculation succeeds, and have Save send `lastRun`. Editing an input after
  calculating does not change what gets saved.
- **Enable Save only after a successful calculation.** Disable it again on Clear/Reset,
  on validation errors and when the request fails.
- **Store numbers, not formatted strings** (new screens). Save the table rows as raw
  numbers; the report builder formats the values and translates the headers.
  Exception: the six older screens keep saving the display strings they always did
  (see Phase 5), so old and new saves go through the same builders.
- **Capture charts with `chart.toBase64Image()` inside the screen's IIFE**, at Save
  time. The Chart.js instance is local to the closure, so the Save handler is
  registered inside the IIFE, not through an inline `onclick`.
- **Use `var`, not `let`/`const`, for top-level state in screens without an IIFE.**
  The screen's script runs again every time it is injected, and a second top-level
  `let` declaration throws a `SyntaxError`.

---

## 3. Phases

### Phase 0: bug fixes — done

Bugs 1–5 from §1.2, plus bug 6.

### Phase 1: backend foundation — done

- **New:** `financial_options/report_registry.py`, with the six existing models moved in.
- **Changed:** `api/views.py` (the single save view, report and rerun reading the
  registry, screen GET views reading `spec.defaults`), `urls.py`, `models.py`
  (`can_rerun`, bug 6), `simulation_list.html`, `report_template.html` (the `tables`
  block).

### Phase 2: FDM European — done

- Choice `FDM_EUROPEAN` ("Finite Difference European").
- `fdm_european.html`: Save button next to Reset in the results card; the snapshot is
  taken in `handleSubmitFDM()` from the server response.
  - **Parameters:** `asset_price`, `exercise_price`, `time_to_expiration`,
    `interest_rate`, `volatility`, `option_type` (numbers).
  - **Results:** `option_price`, `bs_price`, `error_val`, `grid_m`, `grid_n`,
    `break_even`, `max_loss`, `greeks{delta,gamma,theta}`, `price_plot`,
    `diffusion_plot` (both as data URIs), `interpretation`. The second chart is the
    solution of the diffusion equation in log space, so it is stored as
    `diffusion_plot`; the screen card still calls it "Evolution Heatmap".
- **Registry defaults:** the values that were hard-coded in `fdm_european_view`,
  without `grid_price_steps` and `grid_time_steps`, which the template never read.
- **Report:** FDM price, BS price, absolute error, time steps (M), space steps (N),
  break-even and max loss; the Greeks as a nested table; the two charts; the
  interpretation. Labels in pt and en.

### Phase 3: the four strategy screens — done

The same five steps were applied to each screen:

1. `{% csrf_token %}` in the form.
2. Inputs read from `initial_data`, radio buttons checked according to it.
3. The view renders through `_render_screen()`, which passes `spec.defaults`.
4. Save button next to Calculate, the `lastRun` snapshot and the call to the helper.
   Clear now uses `form.reset()` alone, so it goes back to the loaded values (the
   defaults, or the saved run on rerun).
5. Registry entry and `build_*_report` function.

| `model_type` | Parameters (input ids) | Table / results | Chart |
| --- | --- | --- | --- |
| `CALL_PUT_PAYOFF` | `simulationType`, `quantity`, `strikePrice`, `initialValue`, `finalValue`, `divisions` | price · holder payoff · writer payoff | payoff |
| `ASSET_PUT_COMBINATION` | `quantity`, `strikePriceE`, `initialValue`, `finalValue`, `divisions` | price · put per unit · combination (whole position), as on the screen | payoff |
| `BULL_BEAR_SPREAD` | `strategyType`, `strike_long`, `premium_long`, `strike_short`, `premium_short`, `quantity`, `initialValue`, `finalValue`, `divisions` | summary (debit, max risk, max return, break-even, potential return) and price · P/L | P/L |
| `COLLAR` | `quantity`, `purchasePrice`, `strikePrice`, `minStockPrice`, `maxStockPrice`, `divisions` | price · stock · sold call · bought put · total | payoff |

Side fixes: `bull_bear_spread.html` was missing its closing `</script>`, and the
Asset + Put Clear button reset the strike to 110 instead of the default 100.

### Phase 4: Return & volatility — done

First dropped, then done after checking the calculation. The formulas were right
(discrete `(Pₜ − Pₜ₋₁)/Pₜ₋₁`, continuous `ln(Pₜ/Pₜ₋₁)`, sample standard deviation with
`n − 1`; checked against `numpy.std(ddof=1)`), but the screen had these bugs, now fixed:

1. A price of zero or below gave `Infinity%` / `NaN%` with no warning. Prices must now be
   greater than zero.
2. The number of periods was not validated ("Generate Table" was a plain button, so
   `min`/`max` never applied). It is now a whole number between 3 and 100: volatility
   needs at least two returns, so the old minimum of 2 always ended in "N/A".
3. Enter in the periods field ran the calculation instead of generating the table, and
   crashed with a `TypeError` when there was no table yet.
4. Changing the number of periods after generating the table crashed the calculation
   (it read `price_N` inputs that did not exist). It now reads the rows on the screen.
5. The "N/A" message was English only, and the errors were `alert()`s. Errors are now
   shown in the page, in pt and en.
6. A top-level `let returnsChart` threw a `SyntaxError` the second time the screen was
   opened (§2.6). The script is now an IIFE, and it no longer loads its own copy of
   Chart.js (`home.html` already does).

Also changed: the returns are labelled "1 → 2" (the return from period 1 to 2), the
screen shows the mean returns, and volatility is labelled "per period" with a note that
it is not annualized. Regenerating the table keeps the values already typed.

**Copy to Excel** (a user request): a "Copiar tabela (Excel)" button above the results
copies the last calculation as tab-separated text — period, asset value, discrete
return, continuous return, then the mean return and volatility rows. It also carries the asset values, so
the values table has no button of its own. Numbers use the decimal separator of the
screen's language — asset values as typed, returns with 4 decimals — so Excel in that
language reads them as numbers and percentages. It uses `navigator.clipboard` on HTTPS/localhost
and falls back to `execCommand('copy')`. If Phase 7 screens get the same request, move
`tableAsTsv`/`copyText` to a shared static helper like `save_project.js`.

- Choice `RETURN_VOLATILITY` ("Return & Volatility"), migration `0004`.
- **Parameters:** `periods`, `prices` (a list of numbers). `prices` is a `table_params`
  entry, so it appears in the report table and not in the parameters section.
- **Results** (raw fractions): `discrete_returns`, `continuous_returns`,
  `mean_discrete`, `mean_continuous`, `volatility_discrete`, `volatility_continuous`,
  `chart`.
- **Defaults:** `periods: 5`, `prices: [100, 105, 98, 110, 107.5]`, so the screen opens
  with a worked example. The template reads `initial_data` through `json_script` and
  builds the table from it; Clear goes back to those values.
- **Report:** number of returns, mean returns, both volatilities; a table period · asset
  value · discrete return · continuous return (the first period has no return); the
  chart.
- `volatilidade_template` (in `teoria_opcao`) renders through `_render_screen`.

### Phase 5: move the six older screens to the helper — done

Black-Scholes, BSM, GBSM, CRR and both Monte Carlo screens now save through
`saetoSaveProject`. Each screen reads its parameters when Calculate runs and its
results right after they are shown (`read*Parameters()` / `read*Results()`), and
Save is disabled until a calculation succeeds. This also fixed a Monte Carlo bug:
Save used to be enabled as soon as the request was sent, even if the simulation then
failed.

The payload shape did not change (the same keys, and the same display strings such
as `"$2.49"`), so old and new saves render through the same report builders. The
`save-mcs-model/` route was removed.

### Phase 6: the open items — done

The five items §6 used to list.

1. **The six older reports are bilingual now.** `BLACK_SCHOLES_PARAM_LABELS` (shared by
   Black-Scholes, BSM, GBSM and CRR — each model uses the subset it has, in screen
   order) plus `OPTION_TYPE_VALUE_LABELS` on those four and on both Monte Carlo
   screens. Their `build_*_report` functions label every result through `_t`, with the
   wording the screens use ("Valor da Opção" / "Option Value", "Gregas (Medidas de
   Sensibilidade)" / "Greeks (Sensitivity Measures)"). The values themselves are still
   the display strings the screen showed, as in Phase 5.
   Side effects: the CRR report gained the time step, the value of flexibility and the
   risk-neutral probability no longer crashes on a missing `prob` (it renders `-`); the
   American Monte Carlo report gained the convergence chart it was already saving.
2. **Bull/Bear limits `divisions` to 5–50**, like the other three strategy screens. This
   also rules out `divisions = 1`, which divided by zero when building the price range.
3. **Saved HTML is sanitized** — §2.5. The report still renders the fragment that was
   saved; it is cleaned at render time rather than regenerated on the server, so old
   saves keep working and no screen had to change.
4. **Dead code removed:** `download_report` (route, view, and the `os`/`requests`
   imports it was the only user of), `black_scholes_template`,
   `black_scholes_merton_template` and its route, `european_finite_difference_view` and
   its commented-out route, `use_cases/generate_save_pdf.py`, and
   `report/report_mcs.html` (an orphan from the old two-view design, found while
   removing the rest).
5. **Call & Put shows the option type.** The radios read "Call Option" / "Put Option"
   ("Opção de Compra (Call)" / "Opção de Venda (Put)"), which is what the calculation
   always did — the table keeps both the holder and the writer column. The stored
   values stay `buy`/`sell`, so saved projects still re-run, and `value_labels` maps
   them to the new wording.

Also fixed while in there: the report's lattice heading read `request.session.language`
instead of `language`, so it was English on a Portuguese report; the report has
minimal CSS for the Bootstrap classes the saved fragments carry (green in-the-money
cells, `.alert` blocks), since the report page has no Bootstrap; and the footer logo is
loaded from `{% static %}` — the only code that ever set `logo_image` was the
WeasyPrint helper, so the slot had been empty.

### Phase 7: the other modules — to do

Every calculator outside Opções Financeiras. Each screen follows the recipe in §7 and
the rules in §2.6; the notes below are what is specific to each group. Before starting
a screen, check its calculation the way Phase 4 did (formulas against a reference
implementation, input validation, the `let`/IIFE rule, Enter key, pt/en messages) and
fix what is wrong first.

**Where it lives.** Keep the one model, the one registry and the one save endpoint in
`financial_options`, as Phase 4 did for `teoria_opcao`: other apps import
`_render_screen` and `FinantialModelsChoices` from there. The model name
(`FinantialModels`) no longer fits, but renaming it is a migration of its own and not
needed for this phase. "Projetos salvos" is already generic.

**Screens and what each saves.**

| # | Module | Screen | Template | Inputs | Calculated | Output |
| --- | --- | --- | --- | --- | --- | --- |
| 7.1 | Opções Reais | Binomial model | `teoria/binomial_model.html` | `initialValue`, `strikePrice`, `timeToMaturity`, `riskFreeRate`, `volatility`, `steps`, `optionType`, `exerciseStyle` | browser | values, lattice (HTML) |
| 7.2 | Opções Reais | Copeland & Antikarov | `teoria/copeland-antikarov-template.html` | `projectValue`, `discountRate`, `numPeriods`, `numSimulations`, `uncertaintyPercent`, `cf_i`/`sd_i` per period | browser, `Math.random` | volatility, histogram |
| 7.3 | Opções Reais | Herath & Park | `teoria/herath_park.html` | `expectedPV0`, `pv0StdDev`, `discountRate`, `numPeriods`, `numSimulations`, `uncertaintyPercent`, `cf_i`/`sd_i` per period | browser, `Math.random` | volatility, histogram |
| 7.4 | Processos Estocásticos | Markov chains | `processos-estocasticos/cadeia_markov.html` | `num_states`, `states` (transition matrix), `iterations` | server | distribution, chart |
| 7.5 | Processos Estocásticos | Random walk | `processos-estocasticos/random_walk.html` | `steps` | server | matplotlib PNG |
| 7.6 | Processos Estocásticos | Random walk (normal) | `processos-estocasticos/random_walk_normal.html` | `steps`, `paths` | server | charts |
| 7.7 | Processos Estocásticos | Arithmetic Brownian motion | `processos-estocasticos/abm.html` | `X0`, `mu`, `sigma`, `T`, `dt`, `n_simulations` | server | charts |
| 7.8 | Processos Estocásticos | GBM – Monte Carlo | `processos-estocasticos/monte_carlos.html` | `S0`, `mu`, `sigma`, `num_periods`, `num_simulations`, `time_unit` | server | charts, statistics |
| 7.9 | Processos Estocásticos | GBM – Itô | `processos-estocasticos/mbg_ito.html` | `S0`, `mu`, `sigma`, `T`, `dt`, `n_simulations` | server | charts |
| 7.10 | Processos Estocásticos | Mean reversion | `processos-estocasticos/modelo_media.html` | `S0`, `mu`, `kappa`, `sigma`, `T`, `dt`, `n_simulations` | server | charts |
| 7.11 | Processos Estocásticos | Models comparison | `processos-estocasticos/vizualizacao_modelos.html` | `s0`, `t`, `dt`, `mu_gbm`, `sigma_gbm`, `mu_mr`, `sigma_mr`, `kappa_mr` | server | matplotlib PNG |
| 7.12 | Teoria dos Jogos | Prisoner's dilemma | `teoria_dos_jogos/dilema_prisioneiro.html` | `strategy1`, `strategy2`, `iterations` | server, `random.choice` for the random strategy | scores, rounds |

Not included: the overview pages (`random_walk_overview`, `mbg_overview`), `markov.html`
(a chart with no inputs), and **Aplicações**, which points to `to_do`.

**Order.** 7.1 first: it is deterministic and computed in the browser, like the strategy
screens, so it only repeats Phase 3. Then 7.2–7.3, which add the two new problems below.
Then 7.4–7.11, which share the seed work on the server. 7.12 last.

**Problem 1 — random results do not re-run.** No simulator takes a seed today (no
`seed` in `estocasticos/use_cases`, `Math.random` in 7.2–7.3, `random.choice` in 7.12),
so *Simular Novamente* gives different numbers from the saved report, and step 7 of §5
cannot pass. Fix, per screen:

- Add an optional **seed** input to the screen ("Semente" / "Seed"). Empty means a new
  random seed; the seed that was actually used is shown with the results and saved in
  `parameters`, so the rerun fills it in and reproduces the same paths.
- Server: the use cases take `seed` and build their generator with
  `numpy.random.default_rng(seed)` instead of the global `np.random` functions; the view
  returns the seed it used. The prisoner's dilemma uses `random.Random(seed)`.
- Browser (7.2–7.3): a small seeded generator (e.g. mulberry32) in a shared static file
  next to `save_project.js`, used instead of `Math.random`.
- Tests: the same seed gives the same result; no seed gives a seed back.

**Problem 2 — inputs of variable length.** Markov (`states`, an N×N matrix) and
Copeland & Antikarov / Herath & Park (one `cf_i`/`sd_i` pair per period) build their
inputs in JS. Handle them as Phase 4 did with `prices`: save them as lists (`cash_flows`,
`std_devs`, `transition_matrix`), pass `initial_data` to the script through
`json_script`, build the inputs from it on load and on Clear, and list them in
`table_params` so the report shows them as a table.

**Charts.** Screens that get a matplotlib PNG from the server save the data URI they
received; Chart.js screens use `toBase64Image()` inside the IIFE (§2.6). Check the
payload size of the screens that draw many paths (`n_simulations` up to its maximum)
against the 2.5 MB limit and cap the input if needed.

**Also check while in there.** The GET views of `estocasticos` and `teoria_dos_jogos`
render templates directly; move them to `_render_screen` so they get `initial_data`, and
confirm each calculation endpoint has `@login_required`.

**Per screen, done when:** the choice and migration exist, the registry entry and report
builder are in place, the fixture and URL name are in `financial_options/tests.py`, the
coverage tests pass, and the manual check in §5 passes (including a rerun that gives the
same numbers, for the random ones).

---

## 4. Migration and deploy

- `0003_alter_finantialmodels_model_type`: a single `AlterField` on
  `model_type.choices`. No data changes.
- `0004_alter_finantialmodels_model_type`: the same, for `RETURN_VOLATILITY` (Phase 4).
  `PLANO_MARKOWITZ.md` and Phase 7 also add choices, so their migrations start at `0005`;
  whichever lands second depends on the first.
- `save_project.js` is a new static file; `collectstatic` (already in the Dockerfile)
  picks it up.
- The 40-model limit is enforced from this deploy on (bug 6).
- A user who has a Monte Carlo page open from before the deploy gets an error on Save
  (the old route is gone) until they reload the page.
- Routes removed in Phase 6: `simulations/download/<id>/` (`download_report`) and
  `financial_options/black-scholes-merton/` (`black_scholes_merton`). Nothing linked to
  either; the first returned a 500 for every save.
- No data migration for the Call & Put relabelling: `simulationType` keeps its
  `buy`/`sell` values, only the wording on the screen and in the report changed.

---

## 5. Verification

**Automated — done.** `financial_options/tests.py`:

- Save endpoint: anonymous request redirected; invalid JSON and missing fields → 400;
  unknown `model_type` → 400; every registry type saved with `report='online'`;
  the 40-model limit.
- `view_report_view`: renders a fixture payload for every registry type in pt and en
  (title checked); CRR down factor; formatting and translation of a strategy report;
  parameter order; unknown type → 404; another user's report → 404.
- `rerun_simulation_view`: right template and merged `initial_data` for every type;
  an old save gets filled in with defaults; unknown type redirects to the list.
- First load: every screen opens with its registry defaults and saves through the
  shared helper with its own `model_type`.
- Reports in both languages for the six older screens; the CRR probability survives a
  missing `prob`; the sanitizer keeps the tags the fragments use and drops scripts,
  handlers, links and images, both as a unit test and through `view_report_view`.
- Screens: Call & Put asks for an option type in pt and en, and all four strategy
  screens limit the steps to 5–50.
- **Coverage guards:** every value in `FinantialModelsChoices` has a registry entry;
  every registry entry has a test fixture and an existing template; every parameter in
  a fixture has a label in pt and en; every choice value (`option_type`,
  `simulationType`, `strategyType`) has a `value_labels` entry in both languages.

**Front end — done, without login.** Each screen was injected into a test page the way
`home.html` does it, with `fetch`/`$.ajax` stubbed to return real calculation
responses and to record the Save payload. Checked in pt and en: Save disabled on load,
enabled after a calculation, disabled after Clear/Reset and after a failed calculation;
the snapshot ignores inputs edited after calculating; the six older screens send the
same keys as before.

**Manual, per screen — still to do** on the real server, logged in. Everything below
this line needs a real login and a print preview, which is why it is not automated.

For each of the twelve screens (and each Phase 7 screen as it is done), in this order:

1. Open the screen from the sidebar. The inputs are filled in (the registry defaults)
   and **Save is disabled**.
2. Calculate. Results appear and Save becomes enabled.
3. Change an input **without** calculating again, then Save. It saves the calculated
   run, not the edited input.
4. The project shows up in *Projetos salvos* with a name and the two buttons.
5. *Ver Relatório* in **pt**, then switch the language and open it again in **en**:
   the title, the parameter names, the parameter values for the radio/select inputs,
   the result labels and the chart titles all follow the language. No raw key
   (`asset_price`) and no leftover English on a Portuguese report.
6. Print preview (Ctrl+P): the header repeats on the strategy tables, rows are not cut
   in half, the charts are not split across pages, and the footer logo and the notice
   are in place.
7. *Simular Novamente*: the screen opens with the saved inputs, Save is disabled again,
   and calculating gives the same numbers as the saved report.

Worth a look while going through: FDM (two matplotlib charts and the Greeks table),
CRR (the lattice, which is the one report with saved HTML in a table), Bull/Bear (the
summary block above the table), Call & Put (the relabelled radios, and an old save
made before the relabelling, which must still open and re-run) and Return & volatility
(the table is rebuilt from the saved prices on rerun, and opening the screen twice from
the sidebar still calculates).

**Payload size:** measured well under `DATA_UPLOAD_MAX_MEMORY_SIZE` (2.5 MB): about
76 KB for FDM (two matplotlib PNGs) and about 70 KB for a strategy chart.

---

## 6. Open items

The five items this section used to list were done in Phase 6. What is left:

1. **`weasyprint` is still a dependency** (`requirements.txt`, `Pipfile`) although
   nothing imports it since `generate_save_pdf.py` was deleted — and the Dockerfile
   never installed the system libraries it needs, so importing it would have failed
   anyway. Dropping it needs a `pipenv lock` to keep `Pipfile.lock` in step, so it is
   left for a deploy where the lockfile is refreshed on purpose.
2. **Monte Carlo statistic names are not translated.** `statistics` is read from the
   table on the screen, so the keys are in whichever language the screen was in when
   the project was saved; the report prints them as they were saved. Fixing it means
   saving the statistic keys instead of their labels, which changes the payload of a
   screen that has saves in the wild.
3. **`fdm_european_view` returns the diffusion chart as `payoff_plot`.** The screen
   stores it under `diffusion_plot`, which is what the report reads, so nothing is
   broken; the response key is just misleading.
4. **`urls.py` maps `pricing/fdm/european/` twice**, as `european_finite_difference`
   and as `fdm_european_api`. Both names resolve to the same view, so the duplicate is
   harmless, but one of them should go once the overview card is updated.

---

## 7. Recipe for future models

1. Add the choice to `FinantialModelsChoices` and create the migration.
2. Add the registry entry: `template`, `defaults`, `param_labels`, `value_labels` (for
   choice inputs), `table_params` (for list inputs) and `build_report`.
3. Render the screen's GET view with `_render_screen(request, model_type)` (import it
   from `financial_options.api.views` when the screen is in another app). List inputs
   reach the script through `{{ initial_data|json_script:"..." }}`.
4. In the template: `{% csrf_token %}`, inputs read from `initial_data`, a snapshot on
   calculate, Save disabled until then, and `saetoSaveProject(...)`. Follow §2.6.
5. In `financial_options/tests.py`, add a fixture to `FIXTURES` and the screen's URL
   name to `SCREEN_URL_NAMES`; if the screen has a new choice input, add its id to
   `CHOICE_KEYS`. The coverage tests fail until steps 2 and 5 are done: they check the
   registry entry, the template, a label for every parameter and every choice value in
   both languages.
