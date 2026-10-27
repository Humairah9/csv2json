"""Unit tests for the conversion logic (no subprocesses)."""
import io
import unittest

import common  # noqa: F401  (puts src/ on sys.path)
from csv2json.cli import CsvError, convert, infer_value


def conv(text, **options):
    data, _ragged = convert(io.StringIO(text), **options)
    return data


class ConvertTests(unittest.TestCase):
    def test_rows_become_objects_keyed_by_header(self):
        self.assertEqual(conv("id,name\n1,Ada\n2,Bola\n"),
                         [{"id": "1", "name": "Ada"}, {"id": "2", "name": "Bola"}])

    def test_values_stay_text_by_default_so_leading_zeros_survive(self):
        self.assertEqual(conv("zip,phone\n02134,007\n"), [{"zip": "02134", "phone": "007"}])

    def test_quoted_fields_keep_commas_newlines_and_quotes(self):
        text = 'id,note\n1,"line one\nline two, with comma"\n2,"say ""hi"""\n'
        self.assertEqual(conv(text), [{"id": "1", "note": "line one\nline two, with comma"},
                                      {"id": "2", "note": 'say "hi"'}])

    def test_duplicate_column_names_are_rejected(self):
        with self.assertRaises(CsvError) as ctx:
            conv("id,name,name\n1,Ada,Lovelace\n")
        self.assertIn("duplicate column name 'name'", str(ctx.exception))

    def test_wrong_field_count_is_rejected_with_line_number(self):
        with self.assertRaises(CsvError) as ctx:
            conv("a,b,c\n1,2,3\n4,5\n")
        self.assertIn("line 3", str(ctx.exception))

    def test_line_number_points_at_start_of_multiline_row(self):
        with self.assertRaises(CsvError) as ctx:
            conv('a,b\n1,"x\ny"\n3\n')  # the short row "3" is on line 4
        self.assertIn("line 4", str(ctx.exception))

    def test_lenient_mode_pads_short_rows_trims_long_rows_and_reports_lines(self):
        data, ragged = convert(io.StringIO("a,b,c\n1,2\n1,2,3,4\n"), lenient=True)
        self.assertEqual(data, [{"a": "1", "b": "2", "c": None}, {"a": "1", "b": "2", "c": "3"}])
        self.assertEqual(ragged, [2, 3])

    def test_empty_input_is_rejected(self):
        with self.assertRaises(CsvError):
            conv("")
        with self.assertRaises(CsvError):
            conv("\n\n")

    def test_header_only_gives_empty_list(self):
        self.assertEqual(conv("a,b\n"), [])

    def test_blank_lines_are_skipped(self):
        self.assertEqual(conv("\na,b\n1,2\n\n3,4\n\n"), [{"a": "1", "b": "2"}, {"a": "3", "b": "4"}])

    def test_no_header_gives_list_of_lists(self):
        self.assertEqual(conv("1,2\n3,4\n", has_header=False), [["1", "2"], ["3", "4"]])

    def test_custom_delimiter(self):
        self.assertEqual(conv("a;b\n1;2\n", delimiter=";"), [{"a": "1", "b": "2"}])

    def test_infer_types_converts_plain_values(self):
        data = conv("n,f,b,e\n3,2.5,TRUE,\n", infer_types=True)
        self.assertEqual(data, [{"n": 3, "f": 2.5, "b": True, "e": None}])
        self.assertIs(type(data[0]["n"]), int)

    def test_infer_types_never_alters_ambiguous_values(self):
        for text in ["007", "02134", "1_000", " 42 ", "NaN", "Infinity", "-Infinity",
                     "1e999", "+5", "0x10", "1,5", "12abc"]:
            with self.subTest(text=text):
                self.assertEqual(infer_value(text), text)


if __name__ == "__main__":
    unittest.main()
