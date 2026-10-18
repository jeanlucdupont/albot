# ArtifactDump

**Extracted forensic artifacts in. CSV and JSON out.**

ArtifactDump is a standalone Python script derived from [Locard](https://github.com/jeanlucdupont/locard). It reads extracted artifact files directly and exports their records without requiring Locard, a case database, or an AI model.

All processing runs locally.

## Supported artifacts

| Type | Input | Exported information |
| --- | --- | --- |
| `browser` | Chrome or Edge `History` file, with available `-wal` companion | Visits, downloads, URL chains, browser/profile labels, and timestamps |
| `evtx` | Windows `.evtx` file | Event identifiers, provider, channel, computer, timestamps, event data, and original XML |
| `mft` | Extracted NTFS `$MFT` | Record metadata, filenames, parent references, attributes, and separate SI/FN timestamps |
| `prefetch` | Windows `.pf` file | Executable name, run count, retained execution timestamps, referenced files, and volumes |
| `registry` | Extracted Registry hive | Keys, values, decoded data, raw value bytes, key last-write timestamps, and parser warnings |

## Requirements

- Python **3.11 or newer**.
- The `artifactdump.py` file.
- Optional parser packages for the artifact types you want to export.

Browser exports use Python’s standard library and require no additional packages.

Install the other parsers individually:

```powershell
# Windows event logs
python -m pip install python-evtx defusedxml

# NTFS Master File Table
python -m pip install dissect.ntfs

# Windows Prefetch
python -m pip install libscca-python

# Windows Registry
python -m pip install libregf-python
```

Or install all optional parsers:

```powershell
python -m pip install python-evtx defusedxml dissect.ntfs libscca-python libregf-python
```

On Windows, use `py` instead of `python` if needed.

Registry and Prefetch packages contain native components. Installation may require compatible wheels or build tools for your Python version and operating system.

Package installation requires access to the package repository. ArtifactDump itself makes no network requests during export.

## Usage

```text
python artifactdump.py TYPE INPUT --output DIRECTORY [OPTIONS]
```

Each command processes **one extracted artifact file**.

The output directory must not already exist, and its parent directory must exist. ArtifactDump refuses to overwrite previous exports.

Show help:

```powershell
python artifactdump.py --help
```

## Examples

### Chrome history

```powershell
python artifactdump.py browser "C:\Evidence\Chrome\Default\History" --browser chrome --profile Default --output "C:\Exports\chrome"
```

### Edge history

```powershell
python artifactdump.py browser "C:\Evidence\Edge\Default\History" --browser edge --profile Default --output "C:\Exports\edge"
```

Browser exports require both `--browser` and `--profile`. These are analyst-supplied labels; the tool does not infer browser identity from the filename.

Use an acquired, consistent snapshot rather than an active browser profile. If you acquired a WAL file, keep it alongside the main database with the exact companion filename:

```text
History
History-wal
```

ArtifactDump reads browser data through a validated private copy. A nonempty rollback journal causes the snapshot to be rejected.

### Windows event logs

```powershell
python artifactdump.py evtx "C:\Evidence\Security.evtx" --output "C:\Exports\events"
```

### Registry hive

```powershell
python artifactdump.py registry "C:\Evidence\SYSTEM" --output "C:\Exports\registry"
```

Other examples include `SOFTWARE`, `SAM`, `SECURITY`, `NTUSER.DAT`, and `UsrClass.dat`.

Registry transaction logs such as `.LOG1` and `.LOG2` are not supported as hive inputs.

### NTFS Master File Table

```powershell
python artifactdump.py mft 'C:\Evidence\$MFT' --output "C:\Exports\mft"
```

Use single quotes around paths containing `$MFT` in PowerShell to prevent variable expansion.

The parser normally determines the record size from the first MFT record. If you know the required size, specify it explicitly:

```powershell
python artifactdump.py mft 'C:\Evidence\$MFT' --record-size 1024 --output "C:\Exports\mft"
```

### Prefetch

```powershell
python artifactdump.py prefetch "C:\Evidence\APP.EXE-12345678.pf" --output "C:\Exports\prefetch"
```

## Output formats

The default is to generate both CSV and JSON.

CSV only:

```powershell
python artifactdump.py evtx Security.evtx --format csv --output events-csv
```

JSON only:

```powershell
python artifactdump.py registry SYSTEM --format json --output registry-json
```

Both formats explicitly:

```powershell
python artifactdump.py prefetch APP.EXE-12345678.pf --format both --output prefetch-export
```

## Generated files

| File | Contents |
| --- | --- |
| `records.csv` | One row per parsed record, with nested structures stored as JSON cells |
| `records.json` | A JSON array containing parsed records and nested structures |
| `errors.jsonl` | One JSON object per parsing error; empty when no errors were recorded |
| `summary.json` | Source SHA-256, record/error counts, completion status, output hashes, and limitations |

`records.csv` and `records.json` are generated according to the selected format.

### CSV columns

| Column | Contents |
| --- | --- |
| `evidence_id` | Parser-generated record identifier |
| `source_type` | Artifact category |
| `artifact_type` | Record subtype |
| `source_file` | Original input path |
| `file_sha256` | SHA-256 of the input file |
| `locator_json` | Record offset or other source locator |
| `warnings_json` | Parser warnings and interpretation limits |
| `detail_json` | Artifact-specific fields |
| `timestamps_json` | Timestamp slots, original values, and normalization metadata where available |
| `objects_json` | Referenced paths, filenames, URLs, or other objects where available |

CSV files use UTF-8 with a BOM. Potentially formula-like scalar cells receive a leading apostrophe. Text nested inside JSON cells remains unchanged; import those columns as text.

JSON output uses `locator`, `warnings`, `detail`, `timestamps`, and `objects` without the CSV suffixes. Use JSON when preserving native types and null values matters.

### Artifact-specific details

- **Registry:** Value records reference their parent key through `detail.key_id`. Find the matching key record for its path and last-write timestamp. Value creation times are not inferred.
- **MFT:** Names and parent references are exported. Complete filesystem paths are not reconstructed.
- **Prefetch:** Retained execution slots and referenced files are exported. Referenced files are not necessarily executed programs.
- **EVTX:** Original event XML is retained alongside selected fields. Parsing is sequential, without Locard’s EVTX recovery engine.
- **Browser:** Visits and downloads retain separate record types and explicit browser/profile context.

Raw MFT record and Prefetch bytes may appear as base64 in `detail.raw`. Registry values retain base64 `raw_data`. Exports can therefore be larger than the input files.

## Integrity and error handling

ArtifactDump opens original inputs for reading. Browser SQLite queries run against a private copy, including acquired WAL content when supplied.

The source file is hashed before and after export. Browser companion inventory is also checked. Detected changes reject the staged results.

Output files are staged before integrity checks. Publishing multiple files is not a single transaction: an interruption or I/O error during publication can leave already published files. Inspect the output directory after a failed command.

Record-level errors are written to `errors.jsonl`. Successfully parsed records can still be exported.

| Status | Meaning |
| --- | --- |
| `complete` | Parsing finished without recorded errors |
| `partial` | Some records were exported, but errors occurred |
| `failed` | Parsing errors occurred and no records were exported |

A complete export containing zero records does not establish absence of activity.

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Export completed without recorded parsing errors |
| `1` | Setup, integrity, or publication error |
| `2` | Partial or failed parsing; inspect the error report |
| `130` | Interrupted |

## Limitations

ArtifactDump expects extracted artifact files. It does not:

- Acquire locked files from a live system.
- Mount E01, RAW, VHD, or other disk images.
- Parse memory dumps or packet captures.
- Replay Registry transaction logs.
- Decrypt SAM or SECURITY secrets.
- Recover deleted browser records.
- Carve EVTX records or recover corrupt chunks.
- Reconstruct complete MFT paths.
- Correlate artifacts or generate investigative conclusions.

There is no parser watchdog or timeout in this version.

Input symlinks and Windows reparse paths are rejected. Use consistent acquired files in analyst-controlled directories.

Browser records do not prove that a person read a page. A download record does not prove execution. Prefetch does not provide a complete execution history. Registry last-write timestamps describe keys, not individual value creation.

Exports are derived analyst output and do not replace original evidence.

## Validation status

The standalone script was checked with synthetic browser, MFT, Prefetch, and Registry inputs.

Optional parser dependencies imported successfully on Linux with Python 3.12. EVTX binary parsing and Windows compatibility still require acceptance testing against representative artifacts.

## Privacy

ArtifactDump does not upload evidence or make network requests during export.

Output can contain sensitive URLs, paths, Registry data, event details, and raw record bytes. Protect exports as you would the source artifacts.

## Origin and licensing

ArtifactDump derives from [Jean-Luc Dupont’s Locard project](https://github.com/jeanlucdupont/locard). Locard’s parsing components were adapted into a single-file tool with direct CSV/JSON exports.

Project source is provided under [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0).

Optional dependencies retain their own licenses:

| Dependency | License |
| --- | --- |
| python-evtx | Apache-2.0 |
| defusedxml | PSF |
| dissect.ntfs | AGPL-3.0-or-later |
| dissect.cstruct / dissect.util | Apache-2.0 |
| libscca-python / libregf-python | LGPL-3.0-or-later |

The project’s Apache license does not relicense its dependencies.
