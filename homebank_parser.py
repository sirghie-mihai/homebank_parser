#!/usr/bin/env python3
"""Flatten an ING Home'Bank statement into one CSV row per transaction."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, localcontext
from io import StringIO
from pathlib import Path


class ParseError(ValueError):
    """The statement cannot be safely interpreted."""


MONTHS = {
    "ianuarie": 1,
    "februarie": 2,
    "martie": 3,
    "aprilie": 4,
    "mai": 5,
    "iunie": 6,
    "iulie": 7,
    "august": 8,
    "septembrie": 9,
    "octombrie": 10,
    "noiembrie": 11,
    "decembrie": 12,
}
TEXT_COLUMNS = (
    "transaction_type",
    "description",
    "merchant_name",
    "counterparty_name",
    "counterparty_iban",
    "reference",
    "bank_reference",
    "authorization_number",
    "card_number",
    "transaction_details",
    "account_holder",
    "account_iban",
)
OUTPUT_COLUMNS = (
    "transaction_id",
    "booking_date",
    "value_date",
    "transaction_date",
    "transaction_type",
    "amount",
    "debit",
    "credit",
    "currency",
    "intermediate_balance",
    "description",
    "merchant_name",
    "counterparty_name",
    "counterparty_iban",
    "reference",
    "bank_reference",
    "authorization_number",
    "card_number",
    "transaction_details",
    "account_holder",
    "account_iban",
    "source_row",
    "details_json",
    "statement_metadata_json",
    "source_rows_json",
)


def clean(value: str) -> str:
    return " ".join(value.split())


def normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", clean(value).lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def currency_code(value: str) -> str:
    code = value.strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", code):
        raise ValueError("Currency must be a three-letter code, such as RON or EUR")
    return code


def read_rows(content: bytes) -> list[tuple[int, list[str]]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ParseError(
            "The statement must be UTF-8 encoded; export the CSV again"
        ) from exc
    reader = csv.reader(StringIO(text, newline=""), strict=True)
    rows = []
    try:
        while True:
            line = reader.line_num + 1
            row = next(reader, None)
            if row is None:
                break
            rows.append((line, row))
    except csv.Error as exc:
        raise ParseError(f"Malformed CSV near row {reader.line_num}") from exc
    return rows


def find_header(rows: list[tuple[int, list[str]]]) -> tuple[int, dict[str, int]]:
    required = {"data", "detalii tranzactie", "debit", "credit"}
    for index, (_, row) in enumerate(rows):
        names = [normalize(cell) for cell in row]
        if not required.issubset(names):
            continue
        balance_name = next(
            (name for name in ("balanta", "balanta intermediara") if name in names),
            None,
        )
        if balance_name is None:
            raise ParseError("Missing Balanță intermediară; enable it and export again")
        if any(names.count(name) != 1 for name in required | {balance_name}):
            raise ParseError("Duplicate transaction columns in the CSV header")
        columns = {name: names.index(name) for name in required}
        columns["balanta"] = names.index(balance_name)
        return index, columns
    raise ParseError("CSV does not match the ING Home'Bank export format")


def parse_amount(value: str, line: int, label: str) -> Decimal | None:
    value = value.strip()
    if not value:
        return None
    if not re.fullmatch(r"[+-]?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?", value):
        raise ParseError(
            f"Invalid {label} amount on row {line}; expected Romanian number format"
        )
    return Decimal(value.replace(".", "").replace(",", "."))


def booking_date(value: str, line: int) -> date:
    parts = normalize(value).split()
    if len(parts) == 3 and parts[1] in MONTHS:
        try:
            return date(int(parts[2]), MONTHS[parts[1]], int(parts[0]))
        except (ValueError, OverflowError):
            pass
    raise ParseError(f"Invalid booking date on row {line}; expected a Romanian date")


def detail_date(value: str, line: int) -> str:
    if not value:
        return ""
    try:
        day, month, year = (int(part) for part in value.split("-"))
        return date(year, month, day).isoformat()
    except (ValueError, OverflowError) as exc:
        raise ParseError(
            f"Invalid detail date in the transaction starting on row {line}"
        ) from exc


def statement_metadata(rows: list[list[str]]) -> dict[str, str]:
    aliases = {
        "titular cont": "account_holder",
        "titular de cont": "account_holder",
        "titularul contului": "account_holder",
        "account holder": "account_holder",
        "iban": "account_iban",
        "cont": "account_iban",
        "contul": "account_iban",
        "cont iban": "account_iban",
        "numar cont": "account_iban",
        "account iban": "account_iban",
        "moneda": "currency",
        "valuta": "currency",
        "moneda contului": "currency",
        "currency": "currency",
    }
    metadata: dict[str, str] = {}
    for row in rows:
        for index, cell in enumerate(row):
            key, separator, value = cell.partition(":")
            field_name = aliases.get(normalize(key))
            if field_name is None:
                continue
            if not separator or not value.strip():
                value = next((cell for cell in row[index + 1 :] if cell.strip()), "")
            value = clean(value)
            if not value:
                continue
            if field_name == "account_iban":
                match = re.fullmatch(
                    r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", value.replace(" ", "").upper()
                )
                if not match:
                    continue
                value = match[0]
            elif field_name == "currency":
                try:
                    value = currency_code(value)
                except ValueError as exc:
                    raise ParseError("Invalid currency in statement metadata") from exc
            if (
                field_name in ("currency", "account_iban")
                and metadata.get(field_name, value) != value
            ):
                raise ParseError(
                    "Conflicting account or currency metadata; export one account at a time"
                )
            metadata[field_name] = value
    return metadata


@dataclass
class Entry:
    line: int
    day: date
    kind: str
    debit: Decimal | None
    credit: Decimal | None
    balance: Decimal
    rows: list[list[str]] = field(default_factory=list)
    details: list[str] = field(default_factory=list)

    @property
    def amount(self) -> Decimal:
        # copy_negate keeps every decimal digit, independent of context precision.
        return self.credit if self.credit is not None else self.debit.copy_negate()


def transaction_row(
    entry: Entry, metadata: dict[str, str], raw_metadata: str
) -> dict[str, str]:
    details: dict[str, list[str]] = {}
    for line in entry.details:
        key, separator, value = line.partition(":")
        if separator and key.strip():
            details.setdefault(key.strip(), []).append(value.strip())

    def pick(*labels: str) -> str:
        for label in labels:
            for key, values in reversed(list(details.items())):
                if normalize(key) == normalize(label):
                    return clean(values[-1])
        return ""

    value_date = detail_date(pick("Data finalizarii (decontarii)", "Data"), entry.line)
    transaction_date = detail_date(pick("Data autorizarii"), entry.line)
    merchant = pick("Tranzactie la")
    counterparty = pick("Ordonator", "Beneficiar", "Catre")
    transaction_details = pick("Detalii tranzactie", "Detalii")
    subject = merchant or counterparty
    description_parts = [entry.kind]
    if subject:
        description_parts.append(subject)
    if transaction_details and transaction_details != subject:
        description_parts.append(transaction_details)
    description = " - ".join(description_parts)
    fingerprint = "|".join(
        [
            entry.day.isoformat(),
            value_date,
            entry.kind,
            str(entry.debit or ""),
            str(entry.credit or ""),
            merchant,
            counterparty,
            description,
            "|".join(sorted(entry.details)),
        ]
    )
    authorization = pick("Numar autorizare")
    bank_reference = pick("Referinta")
    result = {
        "transaction_id": "ing-csv:"
        + hashlib.sha256(fingerprint.encode()).hexdigest()[:32],
        "booking_date": entry.day.isoformat(),
        "value_date": value_date,
        "transaction_date": transaction_date,
        "transaction_type": entry.kind,
        "amount": format(entry.amount, "f"),
        "debit": format(entry.debit, "f") if entry.debit is not None else "",
        "credit": format(entry.credit, "f") if entry.credit is not None else "",
        "currency": metadata.get("currency", ""),
        "intermediate_balance": format(entry.balance, "f"),
        "description": description,
        "merchant_name": merchant,
        "counterparty_name": counterparty,
        "counterparty_iban": pick("Din contul", "In contul", "Catre contul"),
        "reference": authorization or bank_reference,
        "bank_reference": bank_reference,
        "authorization_number": authorization,
        "card_number": pick("Numar card"),
        "transaction_details": transaction_details,
        "account_holder": metadata.get("account_holder", ""),
        "account_iban": metadata.get("account_iban", ""),
        "source_row": str(entry.line),
        "details_json": json_text(details),
        "statement_metadata_json": raw_metadata,
        "source_rows_json": json_text(entry.rows),
    }
    # Keep numbers numeric while making formula-like text safe for spreadsheets.
    # Original values remain available in the JSON columns.
    for name in TEXT_COLUMNS:
        if result[name].lstrip().startswith(("=", "+", "-", "@")):
            result[name] = "'" + result[name]
    return result


def parse_csv(content: bytes, currency: str | None = None) -> list[dict[str, str]]:
    """Validate the complete statement and return flattened, CSV-ready records."""
    rows = read_rows(content)
    header_index, columns = find_header(rows)
    preamble = [row for _, row in rows[:header_index]]
    metadata = statement_metadata(preamble)
    if currency is not None:
        currency = currency_code(currency)
        if metadata.get("currency", currency) != currency:
            raise ParseError("Supplied currency does not match the statement currency")
        metadata["currency"] = currency
    raw_metadata = json_text({"rows": preamble, "header": rows[header_index][1]})
    entries: list[Entry] = []

    for line, row in rows[header_index + 1 :]:
        if not any(cell.strip() for cell in row):
            continue

        def cell(name: str) -> str:
            index = columns[name]
            return row[index].strip() if index < len(row) else ""

        if cell("data"):
            day = booking_date(cell("data"), line)
            debit = parse_amount(cell("debit"), line, "debit")
            credit = parse_amount(cell("credit"), line, "credit")
            balance = parse_amount(cell("balanta"), line, "balance")
            if not cell("detalii tranzactie"):
                raise ParseError(f"Missing transaction type on row {line}")
            if (debit is None) == (credit is None):
                raise ParseError(
                    f"Expected exactly one debit or credit amount on row {line}"
                )
            if any(amount is not None and amount < 0 for amount in (debit, credit)):
                raise ParseError(
                    f"Debit and credit amounts cannot be negative on row {line}"
                )
            if balance is None:
                raise ParseError(f"Intermediate balance is missing on row {line}")
            entries.append(
                Entry(
                    line, day, cell("detalii tranzactie"), debit, credit, balance, [row]
                )
            )
        else:
            if any(cell(name) for name in ("debit", "credit", "balanta")):
                raise ParseError(f"Amounts found without a booking date on row {line}")
            if not entries:
                raise ParseError(
                    f"Detail row {line} appears before the first transaction"
                )
            entries[-1].rows.append(row)
            if cell("detalii tranzactie"):
                entries[-1].details.append(cell("detalii tranzactie"))

    if not entries:
        raise ParseError("No transactions found in CSV")
    with localcontext() as context:
        numbers = [
            number for entry in entries for number in (entry.balance, entry.amount)
        ]
        integer_digits = max(
            len(number.as_tuple().digits) + number.as_tuple().exponent
            for number in numbers
        )
        fractional_digits = max(-number.as_tuple().exponent for number in numbers)
        context.prec = max(28, max(1, integer_digits) + max(0, fractional_digits) + 2)
        for newer, older in zip(entries, entries[1:]):
            if newer.day < older.day:
                raise ParseError(
                    f"Transactions must be ordered newest to oldest (row {older.line})"
                )
            if newer.balance != older.balance + newer.amount:
                raise ParseError(
                    f"Intermediate balances are inconsistent between rows {newer.line} and {older.line}; "
                    "export the complete statement again"
                )
    return [transaction_row(entry, metadata, raw_metadata) for entry in entries]


def write_csv(path: Path, transactions: list[dict[str, str]]) -> None:
    # Exclusive creation protects both the bank statement and previous results.
    with path.open("x", encoding="utf-8-sig", newline="") as handle:
        try:
            writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
            writer.writeheader()
            writer.writerows(transactions)
            handle.flush()
        except BaseException:
            path.unlink()
            raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert an ING Home'Bank CSV statement into one row per transaction."
    )
    parser.add_argument("input", type=Path, help="Original UTF-8 Home'Bank CSV export")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output path (default: INPUT.transactions.csv)",
    )
    parser.add_argument(
        "--currency",
        type=currency_code,
        help="Account currency if absent from the export, e.g. RON",
    )
    args = parser.parse_args()
    source = args.input.expanduser()
    output = (
        args.output.expanduser()
        if args.output
        else source.with_name(source.stem + ".transactions.csv")
    )
    try:
        if source.resolve() == output.resolve():
            raise ParseError("Input and output must be different files")
        transactions = parse_csv(source.read_bytes(), currency=args.currency)
        write_csv(output, transactions)
    except FileExistsError:
        print(
            "error: Output already exists; choose a new path with --output",
            file=sys.stderr,
        )
        return 1
    except (ParseError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Saved {len(transactions)} transactions to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
