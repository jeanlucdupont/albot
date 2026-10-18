# csvDelta

**Two CSV reports. What changed?**

CSVDelta compares an earlier CSV export with a later one and reports new rows, removed rows, and changed values. It runs locally using Python's standard library. No installation of packages, account, API key, or network access is needed.

Useful for vulnerability exports, software inventories, group membership lists, and firewall rule reports.

## Requirements

Python 3.9 or newer. Download `csvdelta.py`, then run it from a terminal. On Windows, use `py` instead of `python` if needed.

## Quick start

```bash
python csvdelta.py yesterday.csv today.csv --key ID
```

The first file is the **old** report; the second is the **new** report. Choose a column that uniquely identifies each row. Row order does not matter.

For vulnerability reports, a combination of columns may be needed:

```bash
python csvdelta.py yesterday.csv today.csv --key Host CVE Port --ignore "Last Seen" --output vulnerability-changes
```

Column names are case-sensitive. Quote names containing spaces. Key columns must exist in both files, contain nonblank values, and identify a unique row in each file. Duplicate keys cause an error rather than silently replacing rows. Add more key columns when needed.

## Example

`yesterday.csv`:

```csv
ID,Host,Severity,Status
1,server01,High,Open
2,server02,Medium,Open
3,server03,Low,Open
```

`today.csv`:

```csv
ID,Host,Severity,Status
1,server01,Critical,Open
3,server03,Low,Open
4,server04,High,Open
```

Run:

```bash
python csvdelta.py yesterday.csv today.csv --key ID
```

Result: one added row (ID 4), one removed row (ID 2), one changed row (ID 1), and one unchanged row (ID 3).

`changed.csv` contains:

```csv
key:ID,column,before,after
1,Severity,High,Critical
```

Each changed cell gets its own row, so multiple changes to one record are easy to review.

## Output

The default output directory is `csvdelta-output`. It must **not already exist**, preventing accidental replacement of previous results. Use `--output` to choose a fresh directory.

| File | Contents |
| --- | --- |
| `added.csv` | Full rows present only in the new report, using its headers |
| `removed.csv` | Full rows present only in the old report, using its headers |
| `changed.csv` | Key values, column name, previous value, and current value |
| `report.json` | Counts, schema changes, selected keys, ignored columns, and all differences |

CSV files are written as UTF-8 with a BOM for compatibility with Excel. Empty result CSVs still contain headers. Input files are never modified. A write failure can leave a partial output directory; resolve the error and rerun using a new directory.

## Options

| Option | Purpose | Default |
| --- | --- | --- |
| `--key NAME [NAME ...]` | Unique identifying column or combination; required | None |
| `--ignore NAME [NAME ...]` | Skip selected columns when comparing values | None |
| `--output DIRECTORY` | Create reports in a new directory | `csvdelta-output` |
| `--delimiter CHARACTER` | Input separator, shared by both files | Comma |
| `--encoding NAME` | Input encoding, shared by both files | `utf-8-sig` |
| `--help` | Show command help | |

Semicolon-separated input:

```bash
python csvdelta.py old.csv new.csv --key ID --delimiter ";" --output changes
```

Older Windows exports:

```bash
python csvdelta.py old.csv new.csv --key ID --encoding cp1252 --output changes
```

## Comparison rules and limits

- Values are compared as exact text, including case and whitespace. `01` and `1` differ; dates and numbers are not normalized.
- Keys are exact text too. Changing a key produces a removed row and an added row.
- Only shared non-key, non-ignored columns are compared for value changes. Added and removed columns are listed separately in JSON and the console. A matched row can count as unchanged even when the schema changes.
- Ignored columns remain in full added/removed rows. Ignoring a column does not remove it from exported data.
- Headers must be unique and nonblank. Rows with too many or too few fields are rejected. CSV quoting and multiline fields are supported.
- Both reports are loaded into memory. This is a small snapshot comparison tool, not a streaming database diff.
- Reports preserve source values, including strings beginning with spreadsheet formula characters. Review untrusted CSV data before opening it in spreadsheet software.
- Exit code `0` means comparison and export succeeded, including when differences exist. Exit code `1` means an error occurred.

## Privacy

CSVDelta makes no network requests. Inputs and reports stay on your machine. Reports may contain sensitive source data; handle them with the same care as the originals.
