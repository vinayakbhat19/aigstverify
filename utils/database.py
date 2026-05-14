import sqlite3
DB_NAME = "database/invoices.db"


def init_db():

    conn = sqlite3.connect(DB_NAME)

    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT,
            gstin TEXT,
            vendor TEXT,
            total_amount REAL,
            fraud_probability TEXT,
            status TEXT
        )
        """
    )

    conn.commit()
    conn.close()


def save_invoice(
    invoice_number,
    gstin,
    vendor,
    total_amount,
    fraud_probability,
    status
):

    conn = sqlite3.connect(DB_NAME)

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO invoices (
            invoice_number,
            gstin,
            vendor,
            total_amount,
            fraud_probability,
            status
    )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            invoice_number,
            gstin,
            vendor,
            total_amount,
            fraud_probability,
            status
        )
    )

    conn.commit()
    conn.close()


def invoice_exists(invoice_number, gstin):

    conn = sqlite3.connect(DB_NAME)

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT * FROM invoices
        WHERE invoice_number=?
        AND gstin=?
        """,
        (invoice_number, gstin)
    )

    result = cursor.fetchone()

    conn.close()

    return result is not None