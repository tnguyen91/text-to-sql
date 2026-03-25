-- Text-to-SQL Explorer: Database Schema
-- E-commerce sample database (normalized to 3NF)

CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    city TEXT,
    state TEXT,
    joined_date DATE DEFAULT CURRENT_DATE
);

CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    category_id INTEGER REFERENCES categories(id),
    stock_quantity INTEGER DEFAULT 0
);

CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    order_date DATE DEFAULT CURRENT_DATE,
    status TEXT DEFAULT 'pending',
    total_amount DECIMAL(10,2)
);

CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    product_id INTEGER REFERENCES products(id),
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL
);

CREATE TABLE reviews (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    product_id INTEGER REFERENCES products(id),
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    comment TEXT,
    review_date DATE DEFAULT CURRENT_DATE
);

-- Seed data

INSERT INTO categories (name) VALUES
('Electronics'), ('Books'), ('Clothing'), ('Home & Kitchen'), ('Sports');

INSERT INTO customers (name, email, city, state, joined_date) VALUES
('Alice Chen', 'alice@email.com', 'Irvine', 'CA', '2024-01-15'),
('Bob Martinez', 'bob@email.com', 'Los Angeles', 'CA', '2024-02-20'),
('Carol Johnson', 'carol@email.com', 'Seattle', 'WA', '2024-03-10'),
('David Kim', 'david@email.com', 'Portland', 'OR', '2024-04-05'),
('Emma Wilson', 'emma@email.com', 'San Diego', 'CA', '2024-05-12'),
('Frank Lee', 'frank@email.com', 'Denver', 'CO', '2024-06-18'),
('Grace Park', 'grace@email.com', 'Austin', 'TX', '2024-07-22'),
('Henry Davis', 'henry@email.com', 'Phoenix', 'AZ', '2024-08-30'),
('Iris Thompson', 'iris@email.com', 'Irvine', 'CA', '2024-09-14'),
('Jack Brown', 'jack@email.com', 'San Francisco', 'CA', '2025-01-03');

INSERT INTO products (name, price, category_id, stock_quantity) VALUES
('Wireless Headphones', 79.99, 1, 150),
('USB-C Hub', 45.99, 1, 200),
('Mechanical Keyboard', 129.99, 1, 75),
('Python Crash Course', 39.99, 2, 300),
('Clean Code', 44.99, 2, 180),
('Data Science Handbook', 54.99, 2, 120),
('Running Shoes', 89.99, 3, 95),
('Winter Jacket', 149.99, 3, 60),
('Coffee Maker', 69.99, 4, 110),
('Yoga Mat', 29.99, 5, 250),
('Bluetooth Speaker', 59.99, 1, 180),
('Desk Lamp', 34.99, 4, 140),
('Water Bottle', 24.99, 5, 300),
('Backpack', 64.99, 3, 90),
('Standing Desk Pad', 49.99, 4, 85);

INSERT INTO orders (customer_id, order_date, status, total_amount) VALUES
(1, '2025-01-15', 'completed', 125.98),
(1, '2025-02-20', 'completed', 84.98),
(2, '2025-01-22', 'completed', 219.98),
(2, '2025-03-05', 'shipped', 39.99),
(3, '2025-02-14', 'completed', 79.99),
(3, '2025-03-18', 'completed', 174.98),
(4, '2025-01-30', 'completed', 129.99),
(4, '2025-02-28', 'completed', 89.98),
(5, '2025-03-01', 'completed', 149.99),
(5, '2025-03-10', 'pending', 59.99),
(6, '2025-02-05', 'completed', 114.98),
(6, '2025-03-15', 'shipped', 69.99),
(7, '2025-01-18', 'completed', 79.99),
(7, '2025-02-22', 'completed', 94.98),
(8, '2025-03-08', 'completed', 45.99),
(9, '2025-02-12', 'completed', 169.98),
(9, '2025-03-20', 'pending', 29.99),
(10, '2025-03-22', 'pending', 129.99),
(1, '2025-03-18', 'shipped', 54.99),
(3, '2025-03-21', 'pending', 64.99);

INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
(1, 1, 1, 79.99), (1, 2, 1, 45.99),
(2, 4, 1, 39.99), (2, 5, 1, 44.99),
(3, 3, 1, 129.99), (3, 7, 1, 89.99),
(4, 4, 1, 39.99),
(5, 1, 1, 79.99),
(6, 8, 1, 149.99), (6, 13, 1, 24.99),
(7, 3, 1, 129.99),
(8, 10, 1, 29.99), (8, 11, 1, 59.99),
(9, 8, 1, 149.99),
(10, 11, 1, 59.99),
(11, 9, 1, 69.99), (11, 2, 1, 45.99),
(12, 9, 1, 69.99),
(13, 1, 1, 79.99),
(14, 12, 1, 34.99), (14, 11, 1, 59.99),
(15, 2, 1, 45.99),
(16, 3, 1, 129.99), (16, 4, 1, 39.99),
(17, 10, 1, 29.99),
(18, 3, 1, 129.99),
(19, 6, 1, 54.99),
(20, 14, 1, 64.99);

INSERT INTO reviews (customer_id, product_id, rating, comment, review_date) VALUES
(1, 1, 5, 'Amazing sound quality!', '2025-01-20'),
(1, 2, 4, 'Works great, compact design', '2025-01-22'),
(2, 3, 5, 'Best keyboard I have ever owned', '2025-02-01'),
(2, 7, 3, 'Decent but runs a bit small', '2025-02-05'),
(3, 1, 4, 'Very comfortable for long use', '2025-02-20'),
(4, 3, 5, 'Cherry MX switches are perfect', '2025-02-10'),
(5, 8, 4, 'Warm and stylish', '2025-03-05'),
(6, 9, 5, 'Best coffee maker at this price', '2025-02-15'),
(7, 1, 4, 'Good value for money', '2025-01-25'),
(8, 2, 3, 'USB-C ports are a bit loose', '2025-03-12'),
(9, 3, 5, 'Typing on this is so satisfying', '2025-02-18'),
(9, 4, 4, 'Great for beginners', '2025-02-20'),
(3, 13, 5, 'Keeps water cold all day', '2025-03-22'),
(6, 2, 4, 'Solid hub, good port selection', '2025-03-18'),
(4, 5, 5, 'Every developer should read this', '2025-03-01');