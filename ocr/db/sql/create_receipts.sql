CREATE TABLE receipts (
    id INTEGER PRIMARY KEY,
    file_name TEXT NOT NULL,
    added2splitwise BOOL NOT NULL,
    ocr_parsed BOOL NOT NULL
);