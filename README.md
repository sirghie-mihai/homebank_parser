<div align="center">

# 🧾 Home’Bank CSV Parser

**Your bank statement, one transaction per row.**

Convert an ING Home’Bank CSV statement into a structured CSV.
Keep the original transaction details for reference.

**Python 3.9+ · No dependencies · Runs locally**

[Quick start](#quick-start) · [Export guide](#export-from-homebank) · [Output fields](#output-fields) · [Troubleshooting](#troubleshooting)

</div>

## Quick start

You need Python **3.9 or later**. No additional packages are required.

1. [Export your statement](#export-from-homebank) with **Balanță intermediară** enabled.
2. Save [`homebank_parser.py`](homebank_parser.py) in the same folder as the statement.
3. Open a terminal in that folder.
4. Run this command:

```bash
python3 homebank_parser.py statement.csv --currency RON
```

Replace `statement.csv` with your filename. Replace `RON` with your account currency.
On Windows, use `py` instead of `python3` if needed.

A successful run prints a message such as:

```text
Saved 3 transactions to statement.transactions.csv
```

The script saves the output beside the input. It does not change the input or
overwrite existing files. For example, `statement.csv` produces
`statement.transactions.csv`.

### What the result looks like

These fictional transactions show four of the 25 output columns:

| booking_date | description | amount | currency |
| --- | --- | ---: | --- |
| 2026-06-15 | Transfer Home'Bank - Example Friend | -25.50 | RON |
| 2026-06-14 | Incasare - Example Employer | 500.00 | RON |
| 2026-06-13 | Cumparare POS - EXAMPLE CAFE | -95.00 | RON |

- Money out is **negative**. Money in is **positive**.
- Dates use `YYYY-MM-DD`. Amounts use a decimal point: `1.379,50` becomes `1379.50`.
- Missing optional fields stay blank. Card numbers retain the bank’s masking.
- Transactions stay in their original order. The script does not remove duplicates, assign categories, or combine statements.

## Export from Home’Bank

Export one account at a time. Use the Romanian, comma-separated **CSV** format.

1. Log in to **Home’Bank**.
2. Open **Rapoarte**.
3. Select the **download icon** in the upper-right corner.
4. Select **Extras de cont**.
5. Choose the account and a period of **no more than two years**.
6. Enable **Balanță intermediară**. Leave the other optional statement fields off.
7. Select **CSV** as the file format.
8. Select **Descarcă**.

> [!IMPORTANT]
> **Balanță intermediară is required.** The script uses it to check transaction amounts against the running balances.
> Keep all transactions, their detail rows, and the original **newest-to-oldest** order.

Use the downloaded file without changes. The script accepts UTF-8 with or without
a byte-order mark (BOM). It recognizes accented and unaccented column labels,
including `Balanță intermediară` and `Balanta`.

## Usage

```text
python3 homebank_parser.py INPUT [-o OUTPUT] [--currency CODE]
```

| Argument | Purpose |
| --- | --- |
| `INPUT` | Path to the original Home’Bank CSV statement. |
| `-o`, `--output` | Output path. For `statement.csv`, the default is `statement.transactions.csv` in the same folder. The output folder must exist. |
| `--currency` | Three-letter account currency, such as `RON` or `EUR`. Lowercase is also accepted. |
| `-h`, `--help` | Show the command-line help. |

**Choose an output filename.** Use double quotes around paths that contain spaces:

```bash
python3 homebank_parser.py "statement June.csv" -o "transactions June.csv" --currency RON
```

Paths can include folders. A leading `~` refers to your home folder.

**Read the currency from the statement:**

```bash
python3 homebank_parser.py statement.csv
```

The script reads currency labels such as `Moneda`, `Valuta`, and `Currency`.
If the statement has no recognized currency, use `--currency`.
If neither source supplies a currency, the output stays **blank**, with no warning.
The script does not assume RON or convert amounts.
A currency that conflicts with the statement causes an error.

## Open the output in a spreadsheet

The output uses comma-separated UTF-8 with a BOM for accented text.

1. Open your spreadsheet’s **Import / From Text or CSV** command.
2. Select the generated `.transactions.csv` file, or your custom output file.
3. Set the encoding to **UTF-8**.
4. Set the delimiter to **comma**.
5. Import references, card numbers, and IBANs as **text** to preserve leading zeros and formatting.

Text fields that start with `=`, `+`, `-`, or `@` receive a leading apostrophe
to prevent spreadsheet formulas. Numeric amounts keep their signs.
The raw-data JSON columns retain the original cell content.

## Output fields

<details>
<summary><strong>All 25 columns, source labels, and data handling</strong></summary>

Columns appear in this order. Missing optional values are blank.

| Column | Meaning |
| --- | --- |
| `transaction_id` | Content fingerprint with an `ing-csv:` prefix. See the limitations below. |
| `booking_date` | Date from the statement’s main `Data` column. |
| `value_date` | Settlement date from `Data finalizarii (decontarii)`; otherwise from the detail label `Data`. |
| `transaction_date` | Authorization date from `Data autorizarii`. |
| `transaction_type` | Transaction type from the statement, such as `Cumparare POS` or `Incasare`. |
| `amount` | Credit amount or negative debit amount. |
| `debit` | Original debit amount. Blank for a credit. |
| `credit` | Original credit amount. Blank for a debit. |
| `currency` | Account currency from the statement or `--currency`. Blank if neither supplies it. |
| `intermediate_balance` | Account balance immediately after the transaction. |
| `description` | Transaction type, merchant or counterparty, and available transaction details. |
| `merchant_name` | Value of `Tranzactie la`. |
| `counterparty_name` | Value of `Ordonator`, `Beneficiar`, or `Catre`, in that priority order. |
| `counterparty_iban` | Value of `Din contul`, `In contul`, or `Catre contul`, in that priority order. |
| `reference` | Authorization number, or the bank reference if no authorization number is present. |
| `bank_reference` | Value of `Referinta`, kept separately. |
| `authorization_number` | Value of `Numar autorizare`. |
| `card_number` | Value of `Numar card`. |
| `transaction_details` | Value of `Detalii tranzactie`; otherwise from `Detalii`. |
| `account_holder` | Account holder from a recognized statement label. |
| `account_iban` | Account IBAN from a recognized statement label, in uppercase without spaces. |
| `source_row` | Starting line number in the input file, counting from 1. |
| `details_json` | Labeled details, including unknown and repeated labels. Each label has a list of values. Surrounding spaces are removed. |
| `statement_metadata_json` | Original rows before the header, plus the header. Repeated on each output row. |
| `source_rows_json` | Original cells from non-empty transaction and detail rows, including unlabelled notes and extra columns. |

**Text and original data.** Extracted detail and account text has extra whitespace
removed. For a repeated identical detail label, the extracted column uses the last
value. The `statement_metadata_json` and `source_rows_json` columns preserve the
original CSV cell content.

For example, `details_json` can contain repeated or unfamiliar labels:

```json
{"Numar card":["**** 1234"],"Numar autorizare":["731084"],"Extra note":["First value","Second value"]}
```

**Fingerprint limits.** The script creates `transaction_id` locally. It is not a
bank-issued ID. Identical transaction content can produce the same fingerprint.
Overlapping statements can repeat transactions. The script keeps all transactions.

</details>

## Troubleshooting

| Problem | Action |
| --- | --- |
| `python3` is not found | On Windows, try `py`. Otherwise, check that Python is installed and available in your terminal. |
| Missing **Balanță intermediară** or a balance | Export again with **Balanță intermediară** enabled. |
| Inconsistent balances or incorrect transaction order | Download a complete statement. Keep all transactions in their original newest-to-oldest order. |
| Invalid date, amount, or CSV structure | Use the original download. Do not save the input through a spreadsheet. |
| Format not recognized | Use the Romanian Home’Bank CSV account statement described above. PDFs and other banks’ formats are unsupported. |
| Currency mismatch | Check the account currency and correct `--currency`. |
| Conflicting account or currency metadata | Export one account at a time. Use the original file without changes. |
| Output already exists | Choose a different filename with `--output`. |
| No transactions found | Export a period that contains transactions. |
| File or folder not found | Check the input path. Create the output folder if it does not exist. |

<details>
<summary><strong>Validation checks, limits, and exit codes</strong></summary>

Before it creates the output, the script checks the CSV structure, required columns,
dates, transaction order, and account metadata.
Each transaction must have a type, an intermediate balance, and exactly one
non-negative debit or credit amount.

For adjacent transactions, including those on the same day, it checks:

```text
newer balance = older balance + newer signed amount
```

Calculations use exact decimals. This check tests consistency within the supplied
file. It cannot confirm that the file contains your complete account history.
It cannot independently verify the oldest transaction without its preceding balance.

Exit codes are **0** for success, **1** for parsing or file errors, and **2** for
invalid command-line arguments. Error messages go to standard error.

</details>

---

**Privacy:** the script reads and writes local files only. It makes no network
requests and needs no bank credentials. Keep statements and generated files in
a private folder outside the repository.
