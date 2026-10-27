# csv2json

Convert a CSV file to JSON from the command line, **without silently damaging your data**.
Standard library only; no dependencies.

## Install and run (two commands)

```sh
pipx install git+https://github.com/Humairah9/csv2json.git
csv2json yourfile.csv
```

Needs Python 3.9 or newer and [pipx](https://pipx.pypa.io/). If your shell says
`csv2json: command not found` straight after installing, run `pipx ensurepath` and open a new terminal.
No pipx? `python3 -m pip install --user git+https://github.com/Humairah9/csv2json.git` works too.

## Examples

The files below are in [`examples/`](examples/).

```console
$ csv2json examples/people.csv
\[
  {
    "name": "Ada Obi",
    "zip": "02134",
    "city": "Ibadan"
  },
  {
    "name": "Bola Ade",
    "zip": "00501",
    "city": "Lagos, Ikeja"
  }
]
```

Note that `02134` keeps its leading zero. Values stay text unless you ask otherwise:

```console
$ csv2json examples/scores.csv --infer-types --indent 0
\[{"player":"Ada","score":42,"active":true,"notes":null},{"player":"Bola","score":17.5,"active":false,"notes":"late"}]
```

Other separators, files and pipes:

```sh
csv2json examples/export.tsv -d tab          # tab-separated input (also: semicolon, pipe, or any one character)
csv2json people.csv -o people.json           # write to a file instead of the terminal
cat people.csv | csv2json - --indent 0       # read standard input, compact output
csv2json old\_export.csv --encoding latin-1   # files saved by older Excel versions
csv2json raw.csv --no-header                 # first row is data: output is a list of lists
```

## Options

|Option|Meaning|
|-|-|
|`FILE`|CSV file to read; `-` or omitted (when piping) means standard input|
|`-o, --output FILE`|Write JSON to FILE (only written if the whole conversion succeeds)|
|`-d, --delimiter CHAR`|One character, or `comma` `tab` `semicolon` `pipe` `space` (default comma)|
|`-e, --encoding NAME`|Input encoding (default UTF-8; an Excel byte-order mark is removed)|
|`--indent N`|Spaces of indentation; `0` = compact (default 2)|
|`--infer-types`|Convert plain numbers, `true`/`false` and empty cells to JSON types|
|`--no-header`|Treat the first row as data|
|`--lenient`|Pad short rows with `null` and drop extra fields, with a warning|
|`--help`, `--version`||

## How it handles awkward input

|Input|Behaviour|
|-|-|
|`02134`, `007`, `1\_000`, `NaN`, `42`|Kept as text, even with `--infer-types`|
|Duplicate column names|Error naming both columns (JSON keys would overwrite each other)|
|Row with too few or too many fields|Error with the line number; `--lenient` fixes and warns|
|Empty file|Error: "input is empty (no header row found)"|
|Header only|Outputs `\[]`|
|Blank lines|Skipped|
|Quoted fields containing commas, quotes or newlines|Preserved|
|Excel byte-order mark|Removed, so the first column is not named `\\ufeffid`|
|Not UTF-8|Error suggesting `--encoding latin-1`|
|Missing file, a directory, unwritable output|One-line error, no traceback|
|`-o` pointing at the input file|Refused, so the input is never overwritten|
|`csv2json big.csv \| head`|Exits quietly|

Exit status: `0` success, `1` bad input or file problem, `2` wrong usage.
Errors go to standard error as `csv2json: error: ...`, so standard output stays clean JSON.

## Run the tests

```sh
git clone https://github.com/Humairah9/csv2json.git && cd csv2json
python3 -m unittest discover -s tests -v
```

31 tests, standard library only; they run the real command line as a subprocess as well as testing the logic directly.

## Limitations

* The whole file is read into memory, so very large files are not streamed.
* Developed and tested on Python 3.12 on Linux. A GitHub Actions workflow for Python 3.9, 3.11 and 3.13 is included in `.github/workflows/`; it had not been run when this was written.
* No automatic detection of the delimiter or encoding: you say what the file is.

## Design

See [DESIGN\_NOTE.md](DESIGN_NOTE.md) for one decision I changed after testing on awkward input.

## Licence

MIT.

