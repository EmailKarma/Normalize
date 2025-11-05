# Name Normaliser: People vs Business (CSV/XLSX)

A fast, explainable Python utility to clean First and Last names, apply locale-aware casing, and classify rows as **Person**, **Business**, or **Undetermined**. Built for everything from small CSVs to multi-million-row files using chunked processing.

## Why this exists

Name fields get messy: `jOHN`, `DOE`, “Support Team,” or “Global Holdings Inc.” This tool fixes casing, flags obvious businesses, and recognises real people using deterministic rules and lightweight reference lists. No black-box models, no surprises.

## Features

* Smart casing for names: handles particles (`van`, `de`), prefixes (`O'`, `Mc`, `Mac`), and hyphenated names.
* Rules-based classification:

  * **Business**: keywords like `Inc`, `Ltd`, `LLC`, `Group`, or digits and `&`.
  * **Person**: exact matches against reference first/last name lists, with optional fallbacks.
  * **Undetermined**: everything else.
* Email-evidence boost: if the email local-part clearly matches the cleaned first and last names, classify as **Person**.
* Chunked CSV processing for scale.
* Safe audit trail: adds new columns, leaves originals untouched.

## Install

Requires Python 3.9+.

```bash
pip install pandas openpyxl
```

## Usage

Run the script, then provide the path to a CSV or XLSX file when prompted.

```bash
python normalize.py
```

The tool writes a new file beside your source:

```
<original_name>_output.csv
```

## Input and output columns

**Expected inputs**

* `FirstName`, `LastName`, `Email`
  Missing columns are created as empty strings.

**Outputs (appended)**

* `FirstName_Clean`
* `LastName_Clean`
* `Type` one of: `Person`, `Business`, `Undetermined`

**Example**

| FirstName  | LastName     | Email                                                         | FirstName_Clean | LastName_Clean | Type         |
| ---------- | ------------ | ------------------------------------------------------------- | --------------- | -------------- | ------------ |
| john       | DOE          | [john.doe@example.com](mailto:john.doe@example.com)           | John            | Doe            | Person       |
| TEAM       | Support      | [help@company.ca](mailto:help@company.ca)                     | Team            | Support        | Undetermined |
| Global     | Holdings     | [info@global.com](mailto:info@global.com)                     | Global          | Holdings       | Business     |
| jane-marie | o'neill      | [jane.oneill@sample.ca](mailto:jane.oneill@sample.ca)         | Jane-Marie      | O'Neill        | Person       |
| alex       | van der meer | [alex.vandermeer@sample.ca](mailto:alex.vandermeer@sample.ca) | Alex            | van der Meer   | Person*      |

* Classified as **Person** by first-name match plus plausible-surname fallback, or by surname list enrichment, or by email-evidence when present.

## How classification works

1. **Business check**
   If either name field contains business terms (`inc`, `ltd`, `corp`, `llc`, `group`, `holdings`, `consulting`, `agency`, `studio`, `marketing`, `solutions`, `company`, `co.`, `partners`, `associates`, `enterprise`), or the fields contain digits or `&`, classify as **Business**.

2. **Person check (exact)**

   * Clean names with smart casing.
   * All first-name tokens must exactly match the given-names set.
   * At least one last-name token must match the surname set.

3. **Email-evidence boost**
   If the email local-part contains both cleaned first and last names, either concatenated (`firstlast`) or separated by `.`, `_`, or `-`, classify as **Person**.

4. **Plausible-surname fallback**
   If the first name is an exact match and the last name looks like a plausible surname shape, classify as **Person**, unless business or department terms are present.

Otherwise, mark **Undetermined**.

## Reference data

By default, the script downloads open lists at runtime:

* First names (US): `smashew/NameDatabases`
* Surnames (US): `smashew/NameDatabases`

You can enrich these with extras:

* **Local files** you curate, one name per line:

  * `extras_firstnames.txt`
  * `extras_surnames.txt`
* **External URLs** (CSV or TXT, single column), if you prefer fully programmatic sources.

The loader unions all sources into two sets for exact, case-insensitive lookups.

## Performance notes

* CSVs are processed in chunks (default 100,000 rows). Adjust `chunksize` to suit your memory.
* XLSX files are read fully. Convert to CSV if you hit memory limits.

## Limitations

* Deterministic rules are simple and auditable, but not perfect. Rare names missing from the lists will need enrichment, or they fall back to **Undetermined**, unless email evidence or the plausible-surname check applies.
* Department names without business keywords remain **Undetermined** by design.

## Roadmap

* Config file for keywords, chunk size, and feature flags.
* Built-in summary report with counts and sample rows.
* Optional “strict mode” that disables fallbacks.

## Contributing

Issues and PRs welcome. Include a small, anonymised sample and expected output.

## Licence

MIT.
