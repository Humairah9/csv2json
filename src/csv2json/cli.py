"""Command-line interface and conversion logic for csv2json."""
import argparse
import codecs
import csv
import io
import json
import math
import os
import re
import sys

from . import __version__

EXIT_OK = 0
EXIT_ERROR = 1  # bad input or unreadable/unwritable files; argparse itself uses 2

DELIMITER_NAMES = {"comma": ",", "tab": "\t", "semicolon": ";", "pipe": "|", "space": " "}

# Deliberately strict: only text that survives a round trip is treated as a number.
_INT = re.compile(r"-?(?:0|[1-9][0-9]*)")
_FLOAT = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")


class CsvError(Exception):
    """A problem with the input data or files. The message is shown to the user."""


def infer_value(text):
    """Turn a CSV cell into null, bool, int, float or str (used by --infer-types).

    Anything ambiguous stays a string, so identifiers such as '02134' or '007',
    padded values like ' 42 ', and non-JSON numbers like 'NaN' are never altered.
    """
    if text == "":
        return None
    lowered = text.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if _INT.fullmatch(text):
        try:
            return int(text)
        except ValueError:  # absurdly long digit strings
            return text
    if _FLOAT.fullmatch(text):
        number = float(text)
        if math.isfinite(number):
            return number
    return text


def _read_header(reader):
    for row in reader:
        if row:  # skip leading blank lines
            break
    else:
        raise CsvError("input is empty (no header row found)")
    seen = {}
    for position, name in enumerate(row, start=1):
        if name in seen:
            raise CsvError(
                "duplicate column name %r (columns %d and %d); "
                "JSON objects cannot hold two values under one key" % (name, seen[name], position)
            )
        seen[name] = position
    return row


def convert(fh, delimiter=",", infer_types=False, has_header=True, lenient=False):
    """Read CSV from a text file object.

    Returns (data, ragged_lines): data is a list of dicts (or a list of lists when
    has_header is False); ragged_lines lists the line numbers fixed up in lenient mode.
    """
    reader = csv.reader(fh, delimiter=delimiter)
    cell = infer_value if infer_types else (lambda text: text)
    records, ragged = [], []
    try:
        header = _read_header(reader) if has_header else None
        while True:
            start_line = reader.line_num + 1
            try:
                row = next(reader)
            except StopIteration:
                break
            if not row:  # blank line
                continue
            if header is None:
                records.append([cell(value) for value in row])
                continue
            if len(row) != len(header):
                if not lenient:
                    raise CsvError(
                        "line %d: expected %d fields but found %d "
                        "(use --lenient to pad or trim such rows)" % (start_line, len(header), len(row))
                    )
                ragged.append(start_line)
                row = (row + [None] * len(header))[: len(header)]
            records.append({name: (None if value is None else cell(value)) for name, value in zip(header, row)})
    except csv.Error as exc:
        raise CsvError("line %d: %s" % (reader.line_num, exc))
    return records, ragged


def _delimiter(text):
    text = DELIMITER_NAMES.get(text.lower(), text)
    if len(text) != 1:
        raise argparse.ArgumentTypeError(
            "%r is not a single character; use one character or one of: %s" % (text, ", ".join(sorted(DELIMITER_NAMES)))
        )
    return text


def _encoding(name):
    try:
        codecs.lookup(name)
    except LookupError:
        raise argparse.ArgumentTypeError("unknown encoding %r (try utf-8, latin-1, cp1252)" % name)
    return name


def _indent(text):
    try:
        value = int(text)
    except ValueError:
        value = -1
    if value < 0:
        raise argparse.ArgumentTypeError("%r is not a whole number of 0 or more" % text)
    return value


def build_parser():
    parser = argparse.ArgumentParser(
        prog="csv2json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Convert a CSV file to JSON.\n"
            "Each row becomes an object keyed by the header row. Reads FILE, or standard\n"
            "input when FILE is '-' or omitted (and input is piped in)."
        ),
        epilog=(
            "Examples:\n"
            "  csv2json people.csv                      print JSON to the terminal\n"
            "  csv2json people.csv -o people.json       write JSON to a file\n"
            "  csv2json scores.csv --infer-types        turn 3 into a number, true into a boolean\n"
            "  csv2json export.tsv -d tab               tab-separated input\n"
            "  cat people.csv | csv2json - --indent 0   read stdin, compact output\n"
            "\n"
            "Exit status: 0 success, 1 bad input or file problem, 2 wrong usage."
        ),
    )
    parser.add_argument("input", nargs="?", metavar="FILE", help="CSV file to read ('-' for standard input)")
    parser.add_argument("-o", "--output", metavar="FILE", help="write JSON here instead of the terminal")
    parser.add_argument("-d", "--delimiter", type=_delimiter, default=",", metavar="CHAR",
                        help="field separator: one character, or a name such as tab, semicolon, pipe (default: comma)")
    parser.add_argument("-e", "--encoding", type=_encoding, default="utf-8-sig", metavar="NAME",
                        help="input text encoding (default: utf-8; a leading BOM is removed)")
    parser.add_argument("--indent", type=_indent, default=2, metavar="N",
                        help="spaces of indentation; 0 gives compact one-line output (default: 2)")
    parser.add_argument("--infer-types", action="store_true",
                        help="convert plain numbers, true/false and empty cells to JSON types; "
                             "values like 007 or 02134 are always kept as text")
    parser.add_argument("--no-header", action="store_true",
                        help="the first row is data, not column names; output is a list of lists")
    parser.add_argument("--lenient", action="store_true",
                        help="pad short rows with null and drop extra fields instead of failing")
    parser.add_argument("--version", action="version", version="csv2json " + __version__)
    return parser


def _open_input(path, encoding):
    if path == "-":
        return io.TextIOWrapper(sys.stdin.buffer, encoding=encoding, newline="")
    if os.path.isdir(path):
        raise CsvError("'%s' is a directory, not a CSV file" % path)
    try:
        return open(path, "r", encoding=encoding, newline="")
    except OSError as exc:
        raise CsvError("cannot read '%s': %s" % (path, exc.strerror))


def _write_output(text, path):
    payload = (text + "\n").encode("utf-8")
    if path is None:
        stream = getattr(sys.stdout, "buffer", None)
        if stream is not None:
            stream.write(payload)
            stream.flush()
        else:
            sys.stdout.write(text + "\n")
        return
    try:
        with open(path, "wb") as out:
            out.write(payload)
    except OSError as exc:
        raise CsvError("cannot write '%s': %s" % (path, exc.strerror))


def _run(args, parser):
    source = args.input
    if source is None:
        if sys.stdin.isatty():
            parser.error("no input given: name a CSV file, or pipe data in (see --help)")
        source = "-"
    if args.output and source != "-" and os.path.exists(args.output) and os.path.exists(source) \
            and os.path.samefile(source, args.output):
        raise CsvError("output file is the same as the input file; choose a different -o name")

    fh = _open_input(source, args.encoding)
    try:
        data, ragged = convert(fh, args.delimiter, args.infer_types, not args.no_header, args.lenient)
    except UnicodeDecodeError:
        raise CsvError(
            "input is not valid %s text; if it came from Excel or an older system, "
            "try --encoding latin-1 (or cp1252)" % ("UTF-8" if args.encoding == "utf-8-sig" else args.encoding)
        )
    finally:
        if source != "-":
            fh.close()

    if args.indent == 0:
        text = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    else:
        text = json.dumps(data, ensure_ascii=False, allow_nan=False, indent=args.indent)
    _write_output(text, args.output)  # only reached after a fully successful conversion

    if ragged:
        sys.stderr.write(
            "csv2json: warning: fixed %d row(s) with the wrong number of fields (first at line %d)\n"
            % (len(ragged), ragged[0])
        )
    return EXIT_OK


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return _run(args, parser)
    except CsvError as exc:
        sys.stderr.write("csv2json: error: %s\n" % exc)
        return EXIT_ERROR
    except BrokenPipeError:  # e.g. `csv2json big.csv | head`
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        except (OSError, ValueError):
            pass
        return EXIT_OK
    except KeyboardInterrupt:
        sys.stderr.write("csv2json: interrupted\n")
        return 130


if __name__ == "__main__":
    sys.exit(main())
