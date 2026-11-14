# Optional CSV examples

These small files are for manual upload and query exercises. Their names are stable examples, not processing-run or database table names. The automated smoke test creates its own CSV in memory.

| File | Contents | Useful check |
| --- | --- | --- |
| [test-table-1.csv](test-table-1.csv) | Three customer rows with amounts. | Normal upload, processing, and query. |
| [test-table-2.csv](test-table-2.csv) | An order header with no data rows. | Empty-input validation. |
| [test-table-3.csv](test-table-3.csv) | Four customer rows with amounts. | Normal processing and Parquet download. |

For a full reproducible walkthrough with expected totals, use [the smoke test](../README.md#verify-the-workflow).
