# IOCExtract

**Turn a text report into a searchable list of candidate indicators.**

IOCExtract is a single Python script that extracts IP addresses, domains, HTTP/HTTPS URLs, and file-hash-shaped strings from text. It removes duplicates and retains each occurrence's file, line, column, and original text.

Everything runs locally. No additional packages, API keys, or network requests.

## Requirements

Python **3.9 or newer** and `iocextract.py`.

Inputs must be plain text. Save or export emails and reports as text first. The script does not parse PDF, Word, HTML structure, or MIME email attachments.

## Quick start

```powershell
python iocextract.py report.txt --output indicators.json
```

On Windows, use `py` instead of `python` if needed.

CSV output:

```powershell
python iocextract.py report.txt --format csv --output indicators.csv
```

Scan multiple files and deduplicate across them:

```powershell
python iocextract.py report.txt email.txt notes.txt --output indicators.json
```

Include the full source lines:

```powershell
python iocextract.py report.txt --context --output indicators.json
```

Print JSON to the terminal:

```powershell
python iocextract.py report.txt
```

Show help:

```powershell
python iocextract.py --help
```

## Supported indicators

| Type | Handling |
| --- | --- |
| IPv4 | Validated with Python's `ipaddress` library |
| IPv6 | Compressed and normalized with `ipaddress`; standard colon notation, including IPv4-mapped forms |
| Domain | ASCII DNS-style names with an alphabetic suffix of 2–63 characters |
| URL | HTTP/HTTPS, including common `hxxp`/`hxxps` defanging |
| MD5 | 32 hexadecimal characters |
| SHA-1 | 40 hexadecimal characters |
| SHA-256 | 64 hexadecimal characters |

Examples of recognized defanging:

```text
example[.]com
example(.)com
example{.}com
192[.]0[.]2[.]10
hxxps://example[.]com/path
hxxps[:]//example[.]com/path
```

Output values are **refanged**. The original matched text remains in each occurrence's `raw` field. Avoid clicking or browsing extracted URLs unintentionally.

Domains and IP addresses contained within URLs are also extracted as separate indicators. Domains in email addresses can be extracted; complete email addresses are not exported as an indicator type.

## Example

Input:

```text
Investigate hxxps://example[.]com/payload and 192[.]0[.]2[.]10.
The same IP appears again: 192.0.2.10
```

The output contains three unique candidate indicators:

- `https://example.com/payload`
- `example.com`
- `192.0.2.10`

The IP entry contains two occurrences. Line and column numbers start at 1; columns count Python text characters, not encoded bytes.

## Output

JSON is an array of unique indicators:

```json
[
  {
    "type": "domain",
    "value": "example.com",
    "occurrences": [
      {
        "source_file": "C:\\Reports\\report.txt",
        "line": 1,
        "column": 27,
        "raw": "example[.]com"
      }
    ]
  }
]
```

With `--context`, each occurrence also includes the complete source line.

CSV has four columns:

| Column | Contents |
| --- | --- |
| `type` | Indicator category |
| `value` | Normalized/refanged value |
| `occurrence_count` | Number of matched occurrences |
| `occurrences_json` | Source references and original matches as a JSON array |

One row represents one unique type/value pair. JSON structure is retained inside the CSV occurrence column. Import this column as text.

Results are sorted by type and value. Domains and hashes are lowercased. IP addresses use canonical representations. URLs preserve hostname spelling, path, query, and fragment case; scheme spelling is normalized. URLs differing in case or spelling may therefore remain separate entries.

Repeated input paths are scanned once. Existing output files are refused; choose a new filename. Inputs are never modified. A write interruption may leave an incomplete output file.

## Options

| Option | Purpose | Default |
| --- | --- | --- |
| `files` | One or more input text files | Required |
| `--format json\|csv` | Output format | `json` |
| `--output FILE` | Create a new output file | Standard output |
| `--encoding NAME` | Input text encoding | `utf-8-sig` |
| `--context` | Include complete matching source lines | Off |
| `--version` | Show script version | |
| `--help` | Show command help | |

For an older Windows text export:

```powershell
python iocextract.py report.txt --encoding cp1252 --output indicators.json
```

The unique indicator count is written to standard error, keeping redirected output machine-readable.

Exit code `0` means extraction succeeded, including when no indicators were found. Exit code `1` means an input/output or validation error occurred. Invalid command arguments use argparse's exit code `2`.

## Scope and limitations

These are **candidate indicators**, not findings of malicious activity. A domain-shaped filename or version string can be a false positive. Hash length alone does not prove that a string represents a file hash.

- No DNS lookups, reputation checks, enrichment, or URL visits.
- No public-suffix validation; plausible but unregistered domain names can match.
- No Unicode domain conversion, obfuscated hexadecimal/integer IPv4, or spaced-out defanging.
- HTTP and HTTPS URLs only; bare domains are separate domain matches.
- Trailing prose punctuation and unmatched closing brackets are trimmed from URLs. Ambiguous punctuation can still require manual review.
- Plain-text matching cannot reliably distinguish prose, code, filenames, or document formatting.
- All unique indicators and occurrence references are kept in memory. Very large reports or long lines may require substantial memory.
- Output paths, original matches, and optional context can contain sensitive information.

Review the extracted list before using it for blocking or response actions.
