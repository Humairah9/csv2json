"""End-to-end tests: run the real command line as a subprocess."""
import json
import os
import tempfile
import unittest

from common import run_cli


class CliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name

    def write(self, name, content):
        path = os.path.join(self.dir, name)
        with open(path, "wb") as fh:
            fh.write(content if isinstance(content, bytes) else content.encode("utf-8"))
        return path

    def test_help_explains_usage_and_options(self):
        code, out, _ = run_cli("--help")
        self.assertEqual(code, 0)
        for expected in ("usage:", "--infer-types", "--delimiter", "Examples:", "Exit status"):
            self.assertIn(expected, out)

    def test_version(self):
        code, out, _ = run_cli("--version")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("csv2json 1."))

    def test_reads_stdin_and_prints_valid_json(self):
        code, out, _ = run_cli("-", stdin=b"a,b\n1,2\n")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), [{"a": "1", "b": "2"}])

    def test_missing_file_gives_friendly_error_not_a_traceback(self):
        code, out, err = run_cli(os.path.join(self.dir, "nope.csv"))
        self.assertEqual(code, 1)
        self.assertIn("cannot read", err)
        self.assertNotIn("Traceback", err)
        self.assertEqual(out, "")

    def test_directory_as_input_is_rejected(self):
        code, _, err = run_cli(self.dir)
        self.assertEqual(code, 1)
        self.assertIn("is a directory", err)

    def test_bad_delimiter_is_a_usage_error(self):
        code, _, err = run_cli("-d", "ab", "-", stdin=b"a\n")
        self.assertEqual(code, 2)
        self.assertIn("delimiter", err)

    def test_delimiter_names_work(self):
        code, out, _ = run_cli("-d", "tab", "-", stdin=b"a\tb\n1\t2\n")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), [{"a": "1", "b": "2"}])

    def test_output_file_is_written_and_terminal_stays_quiet(self):
        src = self.write("in.csv", "a\n1\n")
        dest = os.path.join(self.dir, "out.json")
        code, out, _ = run_cli(src, "-o", dest)
        self.assertEqual(code, 0)
        self.assertEqual(out, "")
        with open(dest, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), [{"a": "1"}])

    def test_failed_conversion_leaves_no_output_file(self):
        src = self.write("bad.csv", "a,a\n1,2\n")
        dest = os.path.join(self.dir, "out.json")
        code, _, _ = run_cli(src, "-o", dest)
        self.assertEqual(code, 1)
        self.assertFalse(os.path.exists(dest))

    def test_refuses_to_overwrite_its_own_input(self):
        src = self.write("in.csv", "a\n1\n")
        code, _, err = run_cli(src, "-o", src)
        self.assertEqual(code, 1)
        self.assertIn("same as the input", err)
        with open(src) as fh:
            self.assertEqual(fh.read(), "a\n1\n")

    def test_excel_byte_order_mark_is_not_part_of_first_column_name(self):
        src = self.write("bom.csv", b"\xef\xbb\xbfid,name\n1,Ada\n")
        code, out, _ = run_cli(src)
        self.assertEqual(code, 0)
        self.assertEqual(list(json.loads(out)[0]), ["id", "name"])

    def test_non_utf8_file_suggests_encoding_flag_and_flag_works(self):
        src = self.write("latin.csv", "id,name\n1,Jos\xe9\n".encode("latin-1"))
        code, _, err = run_cli(src)
        self.assertEqual(code, 1)
        self.assertIn("--encoding", err)
        self.assertNotIn("Traceback", err)
        code, out, _ = run_cli(src, "--encoding", "latin-1")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)[0]["name"], "Jos\u00e9")

    def test_non_ascii_text_is_not_escaped(self):
        code, out, _ = run_cli("-", stdin="n\nJos\u00e9\n".encode("utf-8"))
        self.assertEqual(code, 0)
        self.assertIn("Jos\u00e9", out)

    def test_empty_file_gives_clear_message(self):
        code, _, err = run_cli(self.write("empty.csv", ""))
        self.assertEqual(code, 1)
        self.assertIn("empty", err)

    def test_ragged_rows_fail_by_default_and_warn_with_lenient(self):
        src = self.write("ragged.csv", "a,b\n1\n")
        code, _, err = run_cli(src)
        self.assertEqual(code, 1)
        self.assertIn("line 2", err)
        code, out, err = run_cli(src, "--lenient")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), [{"a": "1", "b": None}])
        self.assertIn("warning", err)

    def test_indent_zero_gives_compact_output(self):
        code, out, _ = run_cli("--indent", "0", "-", stdin=b"a\n1\n")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), '[{"a":"1"}]')

    def test_infer_types_flag_end_to_end(self):
        code, out, _ = run_cli("--infer-types", "-", stdin=b"zip,n\n02134,7\n")
        self.assertEqual(json.loads(out), [{"zip": "02134", "n": 7}])


if __name__ == "__main__":
    unittest.main()
