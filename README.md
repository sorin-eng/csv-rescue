# CSV Rescue — a $10 import-repair pilot

A small, offline Python tool and a fixed-scope service offer. **Not an n8n workflow, production deployment, or claim of past client work.** Built with AI assistance; demonstrated with tests and explicitly synthetic data. No customers or earnings are claimed.

## Service offer

**10 USDC on Base** for one agreed UTF-8 CSV import repair, up to 5,000 data rows / 10 MiB. Network fees, if any, are paid by the buyer. Scope first; a tiny anonymized preview first; full work only after agreed payment conditions are met.

Deliverables: a cleaned copy, an audit with exact change counts, and a short import note. Possible changes: an explicitly chosen delimiter, UTF-8 BOM removal, opt-in cell-whitespace trimming, and opt-in removal of identical rows. Source stays untouched. Leading zeros and ambiguous dates remain literal. Blank business data is never invented. Different people with the same name/email are never automatically merged.

**Not included:** a whole CRM/n8n automation, scraping, outreach, credentials, production access, Excel formulas/macros, inference of missing facts, or arbitrary broken encodings. If a file needs business decisions or is outside scope, stop and agree a new scope rather than guessing.

Pilot availability and scope must be confirmed before paying. The tool is free under the MIT license; the paid offer is for a processed file and checked results, not access to the code. Do not send money to an address copied from source code. The receive-only payment details are supplied privately only after an agreed scope. No wallet connection, deposit, seed phrase or signature is needed to buy the service.

## Run locally

Python 3.10+, standard library only. No API keys, accounts, installs or network calls.

```sh
python3 csv_rescue.py demo/synthetic-input.csv
python3 csv_rescue.py demo/synthetic-input.csv --output my-cleaned-copy.csv --trim --drop-exact-duplicates --out-delimiter comma
python3 -m unittest -v test_csv_rescue.py
```

Audit is the default and writes no files. Cleanup requires an explicitly named **new** output. Existing files are refused. Headers remain literal; duplicate or blank headers and malformed row widths stop the operation. UTF-8 and UTF-8 BOM are supported; other encodings are refused. Input delimiter detection is a best-effort convenience: use `--delimiter comma|semicolon|tab|pipe` when uncertain. See the chosen delimiter in the report before accepting a cleanup.

Exact-duplicate removal runs **after requested trimming**. Choose it only when identical rows really are duplicates for your import. A file can legitimately contain identical transactions: this tool cannot make that business decision. No fuzzy matching or key-based merging is performed.

## Demo, not a customer case study

`demo/synthetic-input.csv` is deliberately invented test data: made-up names, `.invalid` email addresses, padding, a literal leading-zero ID and duplicate rows. Its imperfections were deliberately introduced to exercise the program. They are not evidence of a paid client's results or market demand. `demo/audit.json`, `demo/cleaned.csv` and `demo/cleanup.json` are real outputs from this file, produced with the commands above.

## Privacy and limitations

- CSV processing stays on the local machine; the program contains no networking or AI calls.
- Audit JSON has column names, counts and hashes, **not data-cell values**. Do not publish real client files, filenames, logs or reports without permission. Never send customer data to a ranking model.
- Cleaned output necessarily contains the original data and is created with owner-only permissions on POSIX systems.
- Reports flag formula-like cells conservatively (including ordinary negative values); they do **not** neutralize formulas or make an unsafe spreadsheet safe to open. Review the file as text before opening it in a spreadsheet.
- The input is never edited. The destination is created exclusively, but a disk/write failure can leave a new partial destination. A failed run is not a successful delivery.
- The tool does not prove that a specific CRM will accept an import. Check that system's requirements and do an authorized dry run before any production import.

## Commercial next step

To discuss a pilot, [open a request](https://github.com/sorin-eng/csv-rescue/issues/new) describing the import problem and expected columns. Use invented example rows only; never put private customer files in a public issue.

Agree the exact sample, permitted transformations, price and delivery checks before full work. Use only the application/contact route invited by a real buyer. No bulk promotion, fabricated portfolio claims, or service ads in hiring-only communities.
