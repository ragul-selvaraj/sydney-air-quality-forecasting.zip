# Forecasting Sydney's PM2.5 Air Pollution — A Day-Ahead Early-Warning System

**Can we forecast Sydney's PM2.5 air pollution one day ahead accurately enough to flag hazardous-air days *before* they happen?**

A time-series analysis built around a real public-health question, using real air-quality data from the NSW Government monitoring network (via the [OpenAQ](https://openaq.org) API). The project deliberately favours **classical statistics, honest validation, and a clear recommendation** over a heavy machine-learning pipeline — because for a single-city day-ahead forecast, that restraint *is* the right engineering judgment.

> **▶️ Run it instantly:** open `notebooks/sydney_air_quality_forecasting_COLAB.ipynb` in Google Colab and choose **Runtime → Run all**. The notebook ships with a built-in synthetic sample, so it runs end-to-end with zero setup — no API key, no downloads. Swap in real data whenever you're ready (see below).

---

## Why this project

PM2.5 — fine particulate matter under 2.5 microns — is the air pollutant most strongly tied to harm to human health. Sydney is the natural Australian case study: it has the country's densest, longest-running air-quality network, and it was blanketed by smoke during the **2019–20 "Black Summer" bushfires**, giving the data a dramatic, uniquely Australian shape. The whole analysis builds toward a recommendation a health agency could actually act on.

## What the notebook does

A complete, honest analyst workflow:

1. **Loads and cleans** real daily PM2.5 — regularises the calendar, handles sensor-downtime gaps with bounded interpolation.
2. **Explores** the series — the winter pollution cycle and the bushfire smoke spike, plus a classical time-series decomposition (trend / seasonal / residual).
3. **Tests stationarity** with the Augmented Dickey-Fuller (ADF) test, and uses differencing to settle the ARIMA `d` parameter.
4. **Reads ACF/PACF** to choose candidate AR and MA orders.
5. **Establishes an honest baseline** — the "tomorrow = today" persistence forecast that any useful model *must* beat.
6. **Validates with walk-forward validation** — refitting at every step and forecasting one day ahead, so there is **no data leakage**. This is the methodological centrepiece.
7. **Reframes the forecast as a binary early-warning classifier** — "hazardous tomorrow, yes/no?" — and measures recall (did we catch the dangerous days?) and precision (did we cry wolf?).
8. **Closes with a public-health recommendation**, candid about where day-ahead forecasting works and where it doesn't (the onset of a bushfire episode being the genuinely hard case).

## Key skills demonstrated

`pandas` time-series indexing & resampling · `matplotlib` / `seaborn` visualisation · `statsmodels` (decomposition, ADF, ACF/PACF, ARIMA) · **walk-forward validation / no data leakage** · baseline-relative evaluation (MAE / RMSE) · a regression-to-classification reframe with recall/precision · programmatic API data ingestion (OpenAQ v3 SDK).

---

## Running the notebook

### The fast path — Colab, zero setup

Open `notebooks/sydney_air_quality_forecasting_COLAB.ipynb` in Colab and **Run all**. The first cell writes a built-in **synthetic** Sydney sample to disk as a fallback, so every cell executes and every chart renders even before you upload anything. This is the synthetic series — realistic winter seasonality and a Black-Summer-style smoke spike — used during development to verify the notebook runs end-to-end. It is **not** a real measurement and should not be used for conclusions.

To run on the real data, use the notebook's **upload cell**: click *Choose Files* and select a `sydney_pm25.csv` (either the real file from `fetch_data.py` below, or `sample_synthetic_sydney_pm25.csv` from this repo). The notebook reads whatever you upload; if you skip the upload, it falls back to the built-in sample automatically.

### Getting the real data

The analysis is designed for **real Sydney PM2.5 data** from the OpenAQ v3 API (which aggregates the NSW Government / DPE air-quality network). Data ingestion is kept separate from analysis — standard practice — via `fetch_data.py`.

**1. Get a free OpenAQ API key**
Register at **https://explore.openaq.org/register** and copy your key.
> Note: OpenAQ retired their v1/v2 API in January 2025. This project uses **v3** only, via the official `openaq` Python SDK.

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Set your key (so it's never committed to git)**
```bash
# macOS / Linux
export OPENAQ_API_KEY="your-key-here"

# Windows (PowerShell)
$env:OPENAQ_API_KEY="your-key-here"
```

**4. Download the data**
```bash
python fetch_data.py
```
This finds the PM2.5 sensors within 25 km of central Sydney, pulls **server-side daily averages** (the v3 `days` rollup), keeps only days with ≥75% hourly coverage, averages the stations into one city-wide series, and writes `sydney_pm25.csv`.

Optional flags:
```bash
python fetch_data.py --start 2019-01-01 --end 2021-12-31 --radius 30000
```

Then upload that `sydney_pm25.csv` into the Colab notebook's upload cell.

---

## A note on reproducibility (read this)

The notebook ships with a **schema-identical synthetic Sydney series** (two columns — `date`, `pm25` daily-average µg/m³) embedded so that "Run all" works offline, purely to verify that every cell runs and every chart renders. That synthetic file is **not** the analytical result. The real OpenAQ data drops into the identical schema and the notebook runs unchanged. The methodology and all conclusions are designed to run on the **real OpenAQ data** obtained via the steps above. The narrative reads dynamically from whatever numbers the data produces, so it stays honest regardless of the exact figures.

---

## Repository structure

```
sydney-air-quality-forecasting/
├── README.md
├── requirements.txt
├── fetch_data.py                              # OpenAQ v3 ingestion -> sydney_pm25.csv (date, pm25)
├── sydney_pm25.csv                            # produced by fetch_data.py (date, pm25)
├── sample_synthetic_sydney_pm25.csv           # synthetic placeholder, identical schema (not real data)
└── notebooks/
    └── sydney_air_quality_forecasting_COLAB.ipynb
```

## Honest limitations

- **Univariate** — the model sees only PM2.5's own past, no weather or fire data. This is why the *onset* of a smoke episode is its weak point, and it's the clearest avenue for improvement (add Open-Meteo wind/temperature drivers next).
- **One pollutant, one city, daily resolution** — the method generalises; the specific numbers don't, and sub-daily spikes are averaged away.
- **Threshold choice** — the 25 µg/m³ "hazardous day" line is a defensible convention, not a law of nature; it should be tuned to an agency's tolerance for false alarms.

---

## Author

**Ragul Balaji Selvaraj** — Melbourne, Australia
Operations professional transitioning into data analytics & data engineering.

- Email: ragulbalajiselvaraj@gmail.com
- LinkedIn: https://www.linkedin.com/in/ragulbalajiselvaraj
- GitHub: https://github.com/ragul-selvaraj

## Data attribution & licence

Air-quality data via [OpenAQ](https://openaq.org), aggregating the NSW Government air-quality monitoring network. Please respect OpenAQ's terms of use. Code released under the MIT Licence.
