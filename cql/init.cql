CREATE KEYSPACE IF NOT EXISTS products
WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

USE products;

CREATE TABLE IF NOT EXISTS products (
    id uuid PRIMARY KEY,
    name text,
    description text,
    price decimal,
    stock int,
    created_at timestamp
);

INSERT INTO products (id, name, description, price, stock, created_at) VALUES
 (uuid(), 'Laptop', 'Lightweight 14-inch laptop', 1099.99, 12, toTimestamp(now())),
 (uuid(), 'Wireless Mouse', 'Ergonomic Bluetooth mouse', 39.99, 120, toTimestamp(now())),
 (uuid(), 'Monitor', '27-inch 1440p IPS monitor', 329.00, 45, toTimestamp(now()));
