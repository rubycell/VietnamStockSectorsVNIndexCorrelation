---
name: import-trades
description: Import TCBS trade history from an uploaded XLSX file into the portfolio database
---

## Instructions

When the user sends or drops an XLSX file (trade history from TCBS), import it into the database:

1. The user will send a file attachment. Get the file URL/path from the message.

2. Download the file, then upload it to the FastAPI backend:
   ```
   curl -X POST $FASTAPI_URL/api/upload -F "file=@<downloaded_file_path>"
   ```

3. Parse the JSON response:
   - `fills_imported`: number of new trade fills added
   - `fills_skipped`: duplicates that were already in the database
   - `invalid_rows`: rows that failed validation
   - `account_type`: detected account type (margin or normal)
   - `batch_id`: import batch ID

4. Report the results to the user:
   - "Imported X trade fills (Y skipped as duplicates)"
   - "Account type: margin/normal"
   - If invalid_rows > 0, mention it

5. After successful import, automatically run the check cycle to update portfolio:
   ```
   curl -X POST $FASTAPI_URL/api/check-cycle
   ```
   Summarize any triggered rules.

## Supported File Format

- TCBS trade history XLSX export
- Bilingual headers (Vietnamese/English)
- Both margin and normal account types
- Duplicate fills are automatically skipped

## Error Handling

- If the file is not .xlsx, tell the user only XLSX files are supported
- If "No valid trades found", the file format may not match TCBS export format
- If "database is locked", ask the user to wait and try again
