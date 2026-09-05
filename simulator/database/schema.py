import sqlite3
from pathlib import Path

DATABASE_PATH = Path("data/processed/merchant.db")

def get_connection()-> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    return connection

def create_tables() -> None:

    connection = get_connection()
    cursor  = connection.cursor()

    cursor.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS customers (
            customer_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            contact TEXT,
            created_at INTEGER NOT NULL,

            lifetime_value_paise INTEGER DEFAULT 0,
            successful_payments INTEGER DEFAULT 0,
            failed_payments INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT NOT NULL,
            status TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL,

            FOREIGN KEY (customer_id)
                REFERENCES customers(customer_id)
        );

        CREATE TABLE IF NOT EXISTS payments (
            payment_id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            entity TEXT NOT NULL DEFAULT 'payment',
            amount REAL NOT NULL,
            currency TEXT NOT NULL,
            status TEXT NOT NULL,
            method TEXT NOT NULL,
            captured INTEGER NOT NULL DEFAULT 0,
            international INTEGER NOT NULL DEFAULT 0,
            description TEXT,
            email TEXT,
            contact TEXT,
            invoice_id TEXT,
            amount_refunded INTEGER DEFAULT 0,
            refund_status TEXT,
            fee INTEGER,
            tax INTEGER,
            error_code TEXT,
            error_description TEXT,
            error_source TEXT,
            error_step TEXT,
            error_reason TEXT,
            bank TEXT,
            vpa TEXT,
            wallet TEXT,
            acquirer_transaction_id TEXT,
            retry_count INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,

            FOREIGN KEY (order_id)
                REFERENCES orders(order_id),

            FOREIGN KEY (customer_id)
                REFERENCES customers(customer_id)
        );

        CREATE TABLE IF NOT EXISTS payment_attempts (
            attempt_id TEXT PRIMARY KEY,
            payment_id TEXT NOT NULL,
            attempt_number INTEGER NOT NULL,
            status TEXT NOT NULL,
            method TEXT NOT NULL,
            amount INTEGER NOT NULL,
            error_code TEXT,
            error_description TEXT,
            error_source TEXT,
            error_step TEXT,
            error_reason TEXT,
            bank TEXT,
            vpa TEXT,
            created_at INTEGER NOT NULL,

            FOREIGN KEY (payment_id)
                REFERENCES payments(payment_id)
        );

         CREATE TABLE IF NOT EXISTS payment_events (
            event_id TEXT PRIMARY KEY,
            payment_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            payload TEXT NOT NULL,

            FOREIGN KEY (payment_id)
                REFERENCES payments(payment_id)
        );

         CREATE TABLE IF NOT EXISTS subscriptions (
            subscription_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            amount INTEGER NOT NULL,
            currency TEXT NOT NULL,
            status TEXT NOT NULL,
            next_billing_date INTEGER NOT NULL,
            failed_attempts INTEGER DEFAULT 0,
            created_at INTEGER NOT NULL,

            FOREIGN KEY (customer_id)
                REFERENCES customers(customer_id)
        );

         CREATE TABLE IF NOT EXISTS invoices (
            invoice_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            amount INTEGER NOT NULL,
            currency TEXT NOT NULL,
            status TEXT NOT NULL,
            due_date TEXT NOT NULL,
            reminder_count INTEGER DEFAULT 0,
            created_at INTEGER NOT NULL,

            FOREIGN KEY (customer_id)
                REFERENCES customers(customer_id)
        );

        CREATE TABLE IF NOT EXISTS recovery_actions (
            action_id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            action_type TEXT NOT NULL,
            reason TEXT,
            status TEXT NOT NULL,
            created_at INTEGER NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_payments_status
        ON payments(status);


        CREATE INDEX IF NOT EXISTS idx_payments_customer
        ON payments(customer_id);


        CREATE INDEX IF NOT EXISTS idx_payments_error
        ON payments(error_code);


        CREATE INDEX IF NOT EXISTS idx_payment_attempts_payment
        ON payment_attempts(payment_id);


        CREATE INDEX IF NOT EXISTS idx_payment_events_payment
        ON payment_events(payment_id);

        CREATE INDEX IF NOT EXISTS idx_invoices_status
        ON invoices(status);


        CREATE INDEX IF NOT EXISTS idx_subscriptions_status
        ON subscriptions(status);
        """
    )

    connection.commit()
    connection.close()

if __name__ == "__main__":
    create_tables()
    print(f"Database created at: {DATABASE_PATH}")