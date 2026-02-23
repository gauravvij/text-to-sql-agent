import sqlite3
import os

def create_ecommerce_db(db_path="ecommerce.db"):
    """
    Creates a sample e-commerce database with multiple tables for testing.
    Includes: Users, Categories, Products, Stocks, Orders, Order_Items, Payments, Reviews.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Users (
        user_id INTEGER PRIMARY KEY,
        username TEXT NOT NULL,
        email TEXT UNIQUE,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        country TEXT
    )
    """)

    # 2. Categories table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Categories (
        category_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT
    )
    """)

    # 3. Products table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Products (
        product_id INTEGER PRIMARY KEY,
        category_id INTEGER,
        name TEXT NOT NULL,
        price REAL NOT NULL,
        description TEXT,
        FOREIGN KEY (category_id) REFERENCES Categories(category_id)
    )
    """)

    # 4. Stocks table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Stocks (
        stock_id INTEGER PRIMARY KEY,
        product_id INTEGER,
        quantity INTEGER DEFAULT 0,
        warehouse_location TEXT,
        FOREIGN KEY (product_id) REFERENCES Products(product_id)
    )
    """)

    # 5. Orders table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Orders (
        order_id INTEGER PRIMARY KEY,
        user_id INTEGER,
        order_date DATETIME DEFAULT CURRENT_TIMESTAMP,
        status TEXT,
        total_amount REAL,
        FOREIGN KEY (user_id) REFERENCES Users(user_id)
    )
    """)

    # 6. Order_Items table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Order_Items (
        item_id INTEGER PRIMARY KEY,
        order_id INTEGER,
        product_id INTEGER,
        quantity INTEGER,
        unit_price REAL,
        FOREIGN KEY (order_id) REFERENCES Orders(order_id),
        FOREIGN KEY (product_id) REFERENCES Products(product_id)
    )
    """)

    # 7. Payments table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Payments (
        payment_id INTEGER PRIMARY KEY,
        order_id INTEGER,
        payment_date DATETIME DEFAULT CURRENT_TIMESTAMP,
        payment_method TEXT,
        amount REAL,
        status TEXT,
        FOREIGN KEY (order_id) REFERENCES Orders(order_id)
    )
    """)

    # 8. Reviews table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Reviews (
        review_id INTEGER PRIMARY KEY,
        product_id INTEGER,
        user_id INTEGER,
        rating INTEGER CHECK(rating >= 1 AND rating <= 5),
        comment TEXT,
        review_date DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES Products(product_id),
        FOREIGN KEY (user_id) REFERENCES Users(user_id)
    )
    """)

    # Insert Sample Data
    cursor.executemany("INSERT OR IGNORE INTO Users (user_id, username, email, country) VALUES (?, ?, ?, ?)", [
        (1, 'alice', 'alice@example.com', 'USA'),
        (2, 'bob', 'bob@example.com', 'UK'),
        (3, 'charlie', 'charlie@example.com', 'Canada')
    ])
    
    cursor.executemany("INSERT OR IGNORE INTO Categories (category_id, name, description) VALUES (?, ?, ?)", [
        (1, 'Electronics', 'Gadgets and devices'),
        (2, 'Clothing', 'Apparel and accessories')
    ])

    cursor.executemany("INSERT OR IGNORE INTO Products (product_id, category_id, name, price, description) VALUES (?, ?, ?, ?, ?)", [
        (1, 1, 'Smartphone', 699.99, 'Latest model'),
        (2, 1, 'Laptop', 1200.00, 'High performance'),
        (3, 2, 'T-Shirt', 19.99, 'Cotton shirt')
    ])

    cursor.executemany("INSERT OR IGNORE INTO Stocks (product_id, quantity, warehouse_location) VALUES (?, ?, ?)", [
        (1, 50, 'New York'),
        (2, 30, 'London'),
        (3, 100, 'New York')
    ])

    cursor.executemany("INSERT OR IGNORE INTO Orders (order_id, user_id, status, total_amount) VALUES (?, ?, ?, ?)", [
        (1, 1, 'Completed', 719.98),
        (2, 2, 'Pending', 1200.00)
    ])

    cursor.executemany("INSERT OR IGNORE INTO Order_Items (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)", [
        (1, 1, 1, 699.99),
        (1, 3, 1, 19.99),
        (2, 2, 1, 1200.00)
    ])

    conn.commit()
    conn.close()
    print(f"Database created at {os.path.abspath(db_path)}")

if __name__ == "__main__":
    create_ecommerce_db()
