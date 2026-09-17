# Sift

Sift is a local-first spreadsheet viewer for triaging cybersecurity vulnerability reports. It opens XLS, XLSX, and CSV files directly in the browser and helps analysts progressively remove irrelevant rows without changing the original file.


## Why Sift?

Vulnerability exports often contain thousands of findings that are not relevant to the current investigation. Filtering them in Excel works, but repeatedly excluding values can become tedious.

Sift treats exclusions as an accumulating list of rules. For example, you can exclude every row containing `CVE-2012-2343`, then add another rule for `CVE-2012-2344`. Both exclusions remain active until you remove or clear them.

## Features

- Open `.xls`, `.xlsx`, and `.csv` files
- Process spreadsheet data locally in the browser
- Work with multiple sheets in a workbook
- Apply cumulative exclusion rules to one column or the entire sheet
- Match values using:
  - Contains
  - Does not contain
  - Equals
  - Starts with
  - Ends with
  - Regular expression
  - Is empty
- Remove individual rules or clear all active exclusions
- Save, load, and delete named exclusion sets in browser storage
- Sort any visible column in ascending or descending order
- Hide and restore columns
- Change the order of columns
- Choose 25, 50, 100, 250, or all rows per page
- Export the remaining visible rows as CSV
- Use the interface on desktop and mobile screens

## Privacy

Imported spreadsheets are parsed in the browser. Sift does not upload their contents to an application server.

Saved exclusion sets are stored in the browser's local storage. They remain on the current device and browser profile until the user deletes them or clears browser data.

## Usage

1. Open Sift.
2. Drop an XLS, XLSX, or CSV file onto the upload area, or select **Open file**.
3. Choose a column—or **Whole sheet**—in the exclusion panel.
4. Select a matching condition and enter a value.
5. Select **Exclude matches**.
6. Add more rules as needed. Every active rule is applied cumulatively.
7. Optionally save the current rules as a named exclusion set.
8. Sort, hide, or reorder columns to organize the remaining data.
9. Select **Export visible rows** to download the current result as CSV.

## Run locally

Sift is a static web application and does not require a build step.

Clone the repository, then serve the `sift` directory with any static HTTP server. For example, with Node.js:

```bash
npx serve sift
```

Open the local address printed by the server.

> Opening `sift/sift.html` directly works in some browsers, but using a local HTTP server provides more consistent behavior.


## Technical notes

- Sift is implemented with HTML, CSS, and vanilla JavaScript.
- Spreadsheet parsing and CSV generation use [SheetJS](https://sheetjs.com/).
- No analytics, account system, or backend database is required.
- Saved filters are browser-specific and are not synchronized between devices.
- Export produces CSV rather than modifying the original workbook.

## Limitations

- Very large workbooks are constrained by available browser memory.
- Spreadsheet formatting, formulas, charts, and macros are not preserved in the exported CSV.
- Saved exclusion sets refer to column names. Loading a set against a file with different columns may produce no matches.

