# TerraSoviet Data Rescue · Track 1: NLP and Document AI

An automated pipeline that turns scanned Soviet geological reports (PDF) into
structured, machine-readable data: JSON, Markdown, and GeoJSON. The project
recognizes Cyrillic text, parses tabular coordinate catalogs, extracts
geological entities (minerals, sites, metal grades), and honestly flags anything
that was recognized with low reliability.

## Table of Contents

1. [What the project does](#what-the-project-does)
2. [How it works](#how-it-works)
3. [Requirements](#requirements)
4. [Installation](#installation)
5. [Running](#running)
6. [Command-line arguments](#command-line-arguments)
7. [What you get as output](#what-you-get-as-output)
8. [Testing](#testing)
9. [Project structure](#project-structure)
10. [Engineering approach](#engineering-approach)
11. [Scope boundaries](#scope-boundaries)
12. [Ready-made examples](#ready-made-examples)

## What the project does

The pipeline covers the full path from scan to structured data:

1. Takes every PDF file from the input folder (recursively, any number of files).
2. Recognizes Cyrillic text via Tesseract OCR with scan preprocessing.
3. Parses coordinate catalogs into structured rows of the form
   "site, latitude, longitude".
4. Extracts geological entities: minerals and metals, grades in g/t,
   coordinates mentioned in the text, the report number.
5. Estimates the mean OCR confidence and flags weakly recognized documents
   with a `needs_review` flag.
6. Saves the result for each document as JSON and Markdown.
7. Assembles corpus-wide artifacts: a coordinate map (GeoJSON), a corpus
   summary, and a list of unique sites after deduplication.
8. Logs every file that could not be processed, without aborting the run.

> **Important note on OCR confidence.** The scans are early-1970s typewritten
> pages on faded paper, so the mean recognition confidence over them is
> objectively low (around 50 percent). The pipeline does not pass such data off
> as accurate: it marks the document as `needs_review` and questionable values
> as `"valid": false` while preserving the raw text. The structure is still
> extracted regardless. Here, low confidence works as a quality indicator, not
> as a recognition failure.

## How it works

The pipeline is split into independent modules, each responsible for one stage.

### Stage 1. Recognition (`ocr.py`)

Each PDF page is rendered to an image (300 dpi) and preprocessed for 1970s
typescript:

* automatic page rotation based on Tesseract OSD data (some appendices are
  scanned rotated by 90 degrees);
* grayscale conversion and contrast equalization (this fixes uneven fading).

We deliberately leave image binarization to Tesseract itself: on the real scans
of this report, the engine's own binarization of the grayscale image yields
noticeably more recognized lines than a manual threshold. Large documents are
rendered in batches so as not to hold hundreds of pages in memory. Each page is
processed in its own error-handling block: one broken page does not bring down
the whole document.

### Stage 2. Coordinate catalog parsing (`parse_catalog.py`)

Tabular catalog rows are parsed with regular expressions. For tables this is
more precise, faster, and fully reproducible. The solution is resilient to
typical Cyrillic OCR errors: digits in coordinates are often recognized as
similar letters (0 and О, 1 and l, 3 and З, 8 and В). Such characters are
allowed in coordinate positions and normalized back into digits. Every row is
checked against a valid range of degrees and minutes. Unreadable or implausible
rows are not silently discarded but marked as `"valid": false`.

### Stage 3. Entity extraction (`entities.py`)

Minerals and metals are searched by word stem, so they are recognized in all
grammatical cases ("золота", "серебром", "медный"). Metal grades are extracted
by a pattern like "13,2 г/т", filtering out values that look like a calendar
year. The report number is determined from context in the text and from the
file name, without confusing the number with a year.

### Stage 4. Assembly and summaries (`main.py`)

The entry point walks all files, writes the result for each document, and at the
end assembles corpus-wide artifacts. The run supports resuming: if a result
already exists for a file, it is skipped, so a run over thousands of files can be
restarted after a failure.

## Requirements

* **Python 3.9 or newer.**
* **Tesseract OCR** with the Russian language pack installed (`rus`).
* **Poppler** (used by the `pdf2image` library to render PDFs).
* Python dependencies from `requirements.txt` (`pytesseract`, `pdf2image`,
  `Pillow`).

## Installation

First install the two system dependencies (Tesseract and Poppler), then the
Python packages. Instructions for each operating system follow.

### Windows

1. Install Tesseract from the UB Mannheim build:
   [github.com/UB-Mannheim/tesseract/wiki](https://github.com/UB-Mannheim/tesseract/wiki).
   During installation, be sure to select the Russian language.
2. Download Poppler for Windows:
   [github.com/oschwartz10612/poppler-windows/releases](https://github.com/oschwartz10612/poppler-windows/releases)
   and add the archive's `bin` folder to the `PATH` environment variable.
3. If `tesseract.exe` is not visible on `PATH`, point to it via an environment
   variable before running (PowerShell):

   ```powershell
   $env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
   ```

### macOS

Install both dependencies via Homebrew:

```bash
brew install tesseract tesseract-lang poppler
```

The `tesseract-lang` package includes the Russian language. After installation,
Tesseract and Poppler are available on `PATH`; no additional configuration is
needed.

### Linux (Ubuntu or Debian)

Install the packages via apt:

```bash
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-rus poppler-utils
```

The `tesseract-ocr-rus` package adds the Russian language, and `poppler-utils`
provides the PDF renderer.

### Python dependencies (all systems)

After installing the system dependencies, install the Python packages:

```bash
pip install -r requirements.txt
```

## Running

Step-by-step scenario for a full run:

1. Create an `input` folder in the project root and place the report PDF files
   into it.
2. Run the pipeline:

   ```bash
   python main.py
   ```

3. Results appear in the `output` folder (created automatically): one `JSON` and
   one `Markdown` file per document, plus the corpus-wide artifacts.

You can specify your own folders instead of the default `input` and `output`.
This is the main scenario for a reviewer whose data lives elsewhere:

```bash
python main.py --input path/to/scans --output path/to/results
```

By default, already-processed files are skipped (resume). To recompute them from
scratch, add the `--overwrite` flag:

```bash
python main.py --overwrite
```

## Command-line arguments

| Argument | Default | Purpose |
| :--- | :--- | :--- |
| `--input` | `input` | Folder with input PDF files (traversed recursively). |
| `--output` | `output` | Folder for results (created automatically). |
| `--overwrite` | disabled | Recompute files for which a result already exists. |

Paths are set only through arguments; there are no hard-coded paths in the code.
This lets you run the pipeline on any dataset without editing the sources.

## What you get as output

### Result per document

For each PDF, a `<name>.json` file is created with the following structure:

```json
{
  "source_file": "каталог_координат_25834.pdf",
  "report_id": "25834",
  "processed_at": "2026-06-27T12:00:00",
  "ocr": {
    "pages": 4,
    "failed_pages": 0,
    "mean_confidence": 78.5,
    "needs_review": false
  },
  "coordinates": [
    {
      "id": "1",
      "name": "Ю.Жуманай",
      "lat_dms": "48°03'",
      "lon_dms": "71°16'",
      "lat_decimal": 48.05,
      "lon_decimal": 71.266667
    }
  ],
  "entities": {
    "minerals": ["висмут", "золото", "серебро"],
    "grades_g_per_t": ["23,9", "13,2"],
    "coordinates_in_text": [
      {"value": "48°03'", "type": "с.ш.", "valid": true, "decimal": 48.05},
      {"value": "71°16'", "type": "в.д.", "valid": true, "decimal": 71.266667}
    ]
  },
  "raw_text": "...full recognized text..."
}
```

A `<name>.md` file with a human-readable summary of the same document is created
alongside it.

### Corpus-wide artifacts

In addition to the per-document result, files covering the entire corpus are
assembled at the end of the run:

| File | Contents |
| :--- | :--- |
| `all_coordinates.geojson` | All valid coordinates from all documents in a single file. Opens on [geojson.io](https://geojson.io). |
| `summary.json` and `summary.md` | Corpus summary: how many documents were processed, how many were flagged `needs_review`, which minerals occur and in how many documents, how many valid coordinates were collected in total. |
| `sites.json` and `sites.md` | Unique sites after cross-document deduplication. The same site (matching name and coordinates) appearing in several reports is collapsed into a single record with a list of sources. Conflicts are called out separately: one name with different coordinates, as a signal for manual review. |
| `_errors.json` | A log of files that could not be processed, with the error text. Created only when failures occur. |

## Testing

The parsing and extraction logic is covered by `pytest` tests. The tests run on
synthetic text and do not require Tesseract or Poppler to be installed, so they
run in any environment:

```bash
pip install pytest
python -m pytest tests/
```

The tests cover, in particular: normalization of OCR digit substitutions in
coordinates, filtering of noise rows, range validation, correct determination of
the report number (without confusing it with a year), and site deduplication. A
separate test verifies that a broken or empty PDF does not crash the run but ends
up in `_errors.json`.

Additionally, the pipeline was run on real documents from report number 25834 of
two different types: a coordinate catalog (tabular data) and a protocol
(continuous text). Both results are in the [`examples/`](examples/) folder. This
is a check against heterogeneous input, since reviewers run the code on a hidden,
similar dataset.

## Project structure

```text
trackone/
├── examples/           ready-made input and output examples (PDF plus JSON, MD, GeoJSON)
├── input/              where input PDF scans go (created by you)
├── output/             where results and the error log are written (created automatically)
├── main.py             entry point: file traversal and assembly of corpus-wide artifacts
├── ocr.py              PDF-to-text recognition (Tesseract, preprocessing, rotation)
├── parse_catalog.py    parsing of tabular coordinate catalogs
├── entities.py         geological entity extraction
├── tests/              pytest tests (no OCR environment required)
├── conftest.py         makes the project root importable for the tests
├── requirements.txt    list of Python dependencies
└── README.md           this file
```

## Engineering approach

The solution is designed against the hackathon criteria.

* **Scalability.** The pipeline processes any number of PDFs in a folder via a
  loop, with no hard-coded file names. Add even 10,000 files and the run works
  the same way.
* **Reproducibility.** Paths are relative and set by arguments, dependencies are
  listed in `requirements.txt`, and the run is a single command.
* **Reliability.** Each file is processed in its own error-protection block. One
  broken scan does not bring down the whole pipeline: it goes into the error log
  while the rest of the files are processed. The run supports resuming after a
  failure.

The core idea follows a mentor's advice: it is better to process most documents
well and honestly flag the rest as needing review than to hard-code rules for
every rare case.

## Scope boundaries

A few things are deliberately not done, so that the solution transfers well to
the hidden dataset.

* **Tables.** Only coordinate catalogs are structured, as the most common and
  valuable tabular structure in these reports. Other tables (for example,
  chemical compositions) are preserved in full in the `raw_text` field of each
  JSON. They can be retrieved from there, but they are not broken down into
  columns. This is a choice in favor of scalability: hard-coded rules for each
  table format transfer poorly to new data.
* **Coordinate datum.** Coordinates are extracted in the document's original
  datum (as a rule, Pulkovo-1942). Conversion to WGS84 belongs to Track 3 and is
  deliberately not performed in this Track 1 solution. The `lat_decimal` and
  `lon_decimal` fields, as well as the GeoJSON, contain the decimal form of the
  original coordinates, not reprojected WGS84 values.

## Ready-made examples

The [`examples/`](examples/) folder contains a complete "input and output" set
that you can study without running anything: the source PDF catalog and the
results generated from it and from the protocol (JSON, Markdown, GeoJSON,
summaries). A detailed description of the examples is provided in
[`examples/README.md`](examples/README.md).
