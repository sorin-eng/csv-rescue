import csv
import hashlib
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

CLI = pathlib.Path(__file__).with_name("csv_rescue.py")

class CSVRescueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="csv-rescue-tests-")
        self.root = pathlib.Path(self.tmp.name)
        self.source = self.root / "input.csv"
    def tearDown(self):
        self.tmp.cleanup()
    def put(self, text, encoding="utf-8"):
        self.source.write_bytes(text.encode(encoding))
        return self.source
    def call(self, *args):
        result = subprocess.run([sys.executable, str(CLI), str(self.source), *map(str,args)],capture_output=True,text=True,timeout=15)
        try: report = json.loads(result.stdout)
        except json.JSONDecodeError: report = {}
        return result, report
    def success(self, *args):
        r,d=self.call(*args)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertTrue(d.get("ok"),d)
        return d
    def test_audit_is_read_only_and_hash_bound(self):
        self.put("id,name\n001,Ada\n002,Lin\n")
        before=self.source.read_bytes(); d=self.success()
        self.assertEqual(d["rows"],2)
        self.assertEqual(d["source_sha256"],hashlib.sha256(before).hexdigest())
        self.assertEqual(self.source.read_bytes(),before)
        self.assertEqual(sorted(x.name for x in self.root.iterdir()),["input.csv"])
    def test_utf8_bom_is_not_part_of_header(self):
        self.put("id,name\n001,Ada\n", "utf-8-sig")
        self.assertEqual(self.success()["columns"],["id","name"])
    def test_semicolon_detection_and_quoted_delimiter(self):
        self.put('id;note\n001;"alpha; beta"\n002;ok\n')
        d=self.success(); self.assertEqual(d["delimiter"],";"); self.assertEqual(d["rows"],2)
    def test_explicit_tab_input_and_comma_output(self):
        self.put("id\tnote\n001\tok\n")
        out=self.root/"clean.csv"; self.success("--delimiter","tab","--out-delimiter",",","--output",out)
        self.assertEqual(out.read_text(),"id,note\n001,ok\n")
    def test_exact_duplicates_are_flagged_not_removed_by_default(self):
        self.put("id,name\n001,Ada\n001,Ada\n002,Lin\n")
        out=self.root/"clean.csv"; d=self.success("--output",out)
        self.assertEqual(d["issues"]["exact_duplicate_rows"],1)
        self.assertEqual(d["output_rows"],3)
    def test_explicit_duplicate_removal_preserves_first(self):
        self.put("id,name\n001,Ada\n001,Ada\n002,Lin\n")
        out=self.root/"clean.csv"; d=self.success("--output",out,"--drop-exact-duplicates")
        self.assertEqual(d["removed_rows"],1)
        self.assertEqual(out.read_text(),"id,name\n001,Ada\n002,Lin\n")
    def test_trim_is_opt_in_and_numeric_and_date_strings_stay_literal(self):
        self.put("id,date,name\n001,01/02/2026, Ada \n")
        one=self.root/"unchanged.csv"; self.success("--output",one)
        self.assertIn(" Ada ",one.read_text())
        two=self.root/"trim.csv"; d=self.success("--output",two,"--trim")
        self.assertEqual(d["trimmed_cells"],1)
        self.assertEqual(two.read_text(),"id,date,name\n001,01/02/2026,Ada\n")
    def test_blank_values_are_not_guessed(self):
        self.put("id,name\n001,\n")
        out=self.root/"clean.csv"; d=self.success("--output",out)
        self.assertEqual(d["issues"]["blank_cells"],1)
        self.assertEqual(out.read_text(),"id,name\n001,\n")
    def test_multiline_quoted_values_survive(self):
        self.put('id,note\n001,"line one\nline two"\n')
        out=self.root/"clean.csv"; d=self.success("--output",out)
        self.assertEqual(d["rows"],1)
        self.assertEqual(list(csv.reader(io.StringIO(out.read_text())))[1][1],"line one\nline two")
    def test_inconsistent_columns_block_output(self):
        self.put("id,name\n001,Ada,extra\n")
        out=self.root/"clean.csv"; r,d=self.call("--output",out)
        self.assertNotEqual(r.returncode,0)
        self.assertEqual(d.get("blocked_reason"),"inconsistent_columns")
        self.assertFalse(out.exists())
    def test_duplicate_headers_block_output(self):
        self.put("id,id\n001,002\n")
        out=self.root/"clean.csv"; r,d=self.call("--output",out)
        self.assertNotEqual(r.returncode,0)
        self.assertEqual(d.get("blocked_reason"),"duplicate_headers")
        self.assertFalse(out.exists())
    def test_empty_headers_block_output(self):
        self.put("id,\n001,Ada\n")
        out=self.root/"clean.csv"; r,d=self.call("--output",out)
        self.assertNotEqual(r.returncode,0)
        self.assertEqual(d.get("blocked_reason"),"blank_headers")
        self.assertFalse(out.exists())
    def test_existing_output_is_not_overwritten(self):
        self.put("id,name\n001,Ada\n")
        out=self.root/"clean.csv"; out.write_text("KEEP ME")
        r,d=self.call("--output",out,"--trim")
        self.assertNotEqual(r.returncode,0)
        self.assertEqual(out.read_text(),"KEEP ME")
        self.assertEqual(d.get("blocked_reason"),"output_exists")
    def test_source_cannot_be_its_own_output(self):
        self.put("id,name\n001,Ada\n"); before=self.source.read_bytes()
        r,d=self.call("--output",self.source)
        self.assertNotEqual(r.returncode,0)
        self.assertEqual(self.source.read_bytes(),before)
        self.assertEqual(d.get("blocked_reason"),"source_is_output")
    def test_reports_never_echo_cell_values(self):
        marker="not-a-client-secret@example.invalid"
        self.put("id,email\n001,"+marker+"\n001,"+marker+"\n")
        r,d=self.call(); self.assertEqual(r.returncode,0,r.stderr)
        self.assertNotIn(marker,r.stdout+r.stderr)
    def test_formula_like_cells_are_warned_not_rewritten(self):
        self.put("id,note\n001,=1+1\n")
        out=self.root/"clean.csv"; d=self.success("--output",out)
        self.assertEqual(d["issues"]["formula_like_cells"],1)
        self.assertIn("=1+1",out.read_text())
    def test_bad_utf8_fails_without_output(self):
        self.source.write_bytes(b"id,name\n001,\xff\n")
        out=self.root/"clean.csv";r,d=self.call("--output",out)
        self.assertNotEqual(r.returncode,0)
        self.assertEqual(d.get("blocked_reason"),"invalid_utf8")
        self.assertFalse(out.exists())
    def test_cleanup_flags_without_output_are_rejected(self):
        self.put("id,name\n001, Ada \n")
        r,d=self.call("--trim")
        self.assertNotEqual(r.returncode,0)
        self.assertEqual(d.get("blocked_reason"),"output_required")
    def test_excessive_rows_are_rejected(self):
        self.put("id\n"+"a\n"*5001)
        r,d=self.call()
        self.assertNotEqual(r.returncode,0)
        self.assertEqual(d.get("blocked_reason"),"row_limit")
    def test_header_only_file_is_valid(self):
        self.put("id,name\n")
        self.assertEqual(self.success()["rows"],0)
    def test_empty_file_is_blocked(self):
        self.put("")
        r,d=self.call(); self.assertNotEqual(r.returncode,0)
        self.assertEqual(d.get("blocked_reason"),"empty_file")
    def test_unterminated_quotes_are_rejected(self):
        self.put('id,note\n001,"not closed\n')
        r,d=self.call("--delimiter",",")
        self.assertNotEqual(r.returncode,0)
        self.assertEqual(d.get("blocked_reason"),"invalid_csv")
    def test_cleaned_file_is_owner_only(self):
        self.put("id,name\n001,Ada\n")
        out=self.root/"clean.csv"; self.success("--output",out)
        self.assertEqual(out.stat().st_mode & 0o777,0o600)

if __name__=="__main__": unittest.main()
