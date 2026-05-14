import sqlite3

conn = sqlite3.connect(
    "database/database.db",
    check_same_thread=False
)

cursor = conn.cursor()

cursor.execute(
    '''
    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_no TEXT,
        gstin TEXT,
        amount REAL
    )
    '''
)

conn.commit()


def save_invoice(
    invoice_no,
    gstin,
    amount
):

    cursor.execute(
        '''
        INSERT INTO invoices (
            invoice_no,
            gstin,
            amount
        )
        VALUES (?, ?, ?)
        ''',
        (
            invoice_no,
            gstin,
            amount
        )
    )

    conn.commit()


def check_duplicate(
    invoice_no,
    gstin
):

    cursor.execute(
        '''
        SELECT * FROM invoices
        WHERE invoice_no=?
        AND gstin=?
        ''',
        (
            invoice_no,
            gstin
        )
    )

    result = cursor.fetchone()

    return result is not None