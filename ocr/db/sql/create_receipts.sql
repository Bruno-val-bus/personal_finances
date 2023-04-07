CREATE TABLE receipts (
    id INTEGER PRIMARY KEY,
    file_name TEXT NOT NULL,
    added2splitwise BOOL NOT NULL,
    ocr_parsed BOOL NOT NULL,
    splitwiseAPI_error TEXT,
    partially_shared BOOL not NULL,
    splitwise_description TEXT not NULL
);