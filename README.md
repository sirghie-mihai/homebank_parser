<div align="center">

# 🧾 Home’Bank CSV Parser

**Your bank statement, one transaction per row.**

Turn an ING Home’Bank CSV export into a clean, structured CSV while keeping
the original transaction details alongside it.

**Python 3.9+ · No dependencies · Runs locally**

[Quick start](#quick-start) · [Export guide](#export-from-homebank) · [Output fields](#output-fields) · [Troubleshooting](#troubleshooting)

</div>

---

Home’Bank spreads each transaction across several rows: the amount on one,
the merchant on another, then dates, references, and more. This script combines
them into **one row per transaction**, ready for analysis or a spreadsheet.

```mermaid
flowchart LR
    A[Home’Bank CSV export] --> B[Parse details and check balances]
    B --> C[Structured transaction CSV]
```

## Quick start

1. [Export your statement](#export-from-homebank) with intermediate balances.
2. Download [`homebank_parser.py`](homebank_parser.py) into a folder on your computer.
3. Open a terminal in that folder and run:

```bash
python3 homebank_parser.py statement.csv --currency RON
```

Use your account’s currency in place of `RON`. On Windows, use `py` if
`python3` is unavailable. Python **3.9 or newer** is the only requirement;
there is nothing to install with `pip`.

```text
Saved 3 transactions to statement.transactions.csv
```

The output is saved next to the input. The original statement stays untouched,
and existing output files are never overwritten.

## Export from Home’Bank

Follow this sequence for each account and period:

| Step | What to do |
| :---: | --- |
| **1** | Log in to **Home’Bank**. |
| **2** | Open **Rapoarte**. |
| **3** | Click the **download icon** in the upper-right corner. |
| **4** | Choose **Extras de cont**, the account, and the desired period. |
| **5** | Select only **Balanță intermediară** among the optional statement fields, and choose **CSV** as the format. |
| **6** | Keep each exported interval to **no more than two years**. |
| **7** | Click **Descarcă** and keep the downloaded file unchanged. |

> [!IMPORTANT]
> **Balanță intermediară is required.** It lets the script check that the
> transaction amounts agree with the running balances. Keep all transactions
> in their original **newest-to-oldest** order, including their detail rows.

The supported input is the Romanian, comma-separated, UTF-8 statement export
(with or without a byte-order mark). The script recognizes accented and
unaccented column labels, including `Balanță intermediară` and `Balanta`.
Export one account at a time and run the script separately for each file.

## Usage

```text
python3 homebank_parser.py INPUT [-o OUTPUT] [--currency CODE]
```

| Argument | Purpose |
| --- | --- |
| `INPUT` | Path to the original Home’Bank CSV statement. |
| `-o`, `--output` | Optional destination. Defaults to `<input-name>.transactions.csv` beside the input. The destination folder must already exist. |
| `--currency` | Three-letter account currency, such as `RON` or `EUR`. Case-insensitive. |
| `-h`, `--help` | Show the command-line help. |

**Choose a destination and use paths containing spaces:**

```bash
python3 homebank_parser.py "~/Downloads/statement June.csv" \
  --output "~/Documents/transactions June.csv" \
  --currency RON
```

**Use currency from the statement when available:**

```bash
python3 homebank_parser.py statement.csv
```

Currency is read from a recognized metadata label such as `Moneda`, `Valuta`,
or `Currency`. If the export does not identify it and you omit `--currency`,
the output currency is **blank**. The script never assumes RON or converts
amounts. A supplied currency that conflicts with the statement causes an error.

## What the result looks like

An abbreviated view of a fictional statement after conversion:

| booking_date | transaction_type | amount | currency | counterparty_name | merchant_name | intermediate_balance |
| --- | --- | ---: | --- | --- | --- | ---: |
| 2026-06-15 | Transfer Home'Bank | -25.50 | RON | Example Friend | | 1379.50 |
| 2026-06-14 | Incasare | 500.00 | RON | Example Employer | | 1405.00 |
| 2026-06-13 | Cumparare POS | -95.00 | RON | | EXAMPLE CAFE | 905.00 |

- **Money out is negative; money in is positive.** Original debit and credit
  amounts also have their own columns.
- Dates use **`YYYY-MM-DD`**. Amounts use a decimal point and no thousands
  separator: `1.379,50` becomes `1379.50`. Arithmetic uses exact decimals.
- Missing optional fields stay **blank**. Card numbers remain exactly as
  disclosed by the bank, including any masking.
- Output follows the statement’s original order. Every parsed transaction is
  written; the script does not deduplicate, categorize, or merge files.

### Output fields

The output contains these 25 columns, in this order:

| Column | Meaning |
| --- | --- |
| `transaction_id` | Repeatable fingerprint of transaction content, prefixed with `ing-csv:`. |
| `booking_date` | Date in the statement’s main `Data` column. |
| `value_date` | Settlement date from `Data finalizarii (decontarii)`, falling back to detail label `Data`. |
| `transaction_date` | Authorization date from `Data autorizarii`, when present. |
| `transaction_type` | Original transaction type, such as `Cumparare POS` or `Incasare`. |
| `amount` | Signed account movement: credit or negative debit. |
| `debit` | Original debit amount, or blank for a credit. |
| `credit` | Original credit amount, or blank for a debit. |
| `currency` | Account currency from recognized metadata or `--currency`; otherwise blank. |
| `intermediate_balance` | Account balance immediately after this transaction. |
| `description` | Transaction type, merchant or counterparty, and transaction details combined. |
| `merchant_name` | Value of `Tranzactie la`. |
| `counterparty_name` | Value of `Ordonator`, `Beneficiar`, or `Catre`, in that priority order. |
| `counterparty_iban` | Value of `Din contul`, `In contul`, or `Catre contul`, in that priority order. |
| `reference` | Authorization number if present; otherwise the bank reference. |
| `bank_reference` | Value of `Referinta`, preserved separately. |
| `authorization_number` | Value of `Numar autorizare`. |
| `card_number` | Value of `Numar card`. |
| `transaction_details` | Value of `Detalii tranzactie`, falling back to `Detalii`. |
| `account_holder` | Account holder from a recognized statement metadata label, when available. |
| `account_iban` | Account IBAN from a recognized statement metadata label, when available. |
| `source_row` | Starting line number of the transaction in the original file, counting from 1. |
| `details_json` | All labeled transaction details, including unknown and repeated labels. Each label maps to a list of values. |
| `statement_metadata_json` | Original preamble rows and column header, repeated on each transaction. |
| `source_rows_json` | All original CSV cells belonging to the transaction, including unlabelled notes and extra columns. |

**The JSON columns keep the source information available.** For example:

```json
{"Numar card":["**** 1234"],"Numar autorizare":["731084"],"Extra note":["First value","Second value"]}
```

Extracted detail and account text collapses whitespace; the JSON columns preserve
the original cell content. For a repeated recognized detail label, the last value
is used in the corresponding normalized column.

The fingerprint is generated locally; it is **not a bank-issued ID**. Two
identical transactions can share a fingerprint, and overlapping statements
can repeat transactions. All rows are retained.

### Open the output in a spreadsheet

The output is comma-separated UTF-8 with a byte-order mark for accented text.
If your spreadsheet opens it as one column, use **Import / From Text or CSV**
and select **UTF-8** and **comma** as the delimiter. Import references, card
numbers, and IBANs as **text** to preserve leading zeros and formatting.

Text fields starting with `=`, `+`, `-`, or `@` receive a leading apostrophe
so spreadsheets treat them as text. Numeric amounts keep their signs. The
unaltered text remains in the JSON columns.

## Troubleshooting

Before creating the output, the script checks dates, transaction types,
debit/credit amounts, intermediate balances, and transaction ordering. For
each adjacent pair of transactions, it verifies:

```text
newer balance = older balance + newer signed amount
```

This also applies to transactions on the same day. It checks consistency
within the supplied file; it cannot prove that the exported period includes
your entire history or independently verify the oldest transaction without
its preceding balance.

| Problem | How to fix it |
| --- | --- |
| Missing **Balanță intermediară** or a missing balance | Export again with **Balanță intermediară** enabled. |
| Inconsistent balances | Download a fresh, complete statement. Keep every transaction and its original order. |
| Transactions must be ordered newest to oldest | Use the original export without sorting or reversing it. |
| Invalid date, amount, or malformed CSV | Use the original download. Avoid saving it through a spreadsheet before parsing. |
| Format not recognized | Check that the input is the Romanian Home’Bank **CSV** account statement described above. PDFs and other banks’ formats are unsupported. |
| Currency mismatch | Check the account currency and correct `--currency`. |
| Output already exists | Choose a different destination with `--output`. |
| No transactions found | Export a period that contains transactions. |
| File or folder not found | Check the input path and create the output folder if needed. |

Successful runs exit with code `0`. Parsing and file errors print a short
message to standard error and exit with code `1`; invalid command-line
arguments exit with code `2`.

---

**Private by design:** the script reads and writes local files only. It makes
no network requests and needs no bank credentials. Keep downloaded statements
and generated files in a private folder outside the repository.
