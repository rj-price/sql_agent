
-- SQL Agent Test Database
-- Creates a sample e-commerce schema for testing the SQL Agent

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    price DECIMAL(10, 2) NOT NULL,
    stock INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'pending',
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS order_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- Insert sample Users
INSERT INTO users (first_name, last_name, email) VALUES
('Jordan', 'Price', 'jordan@example.com'),
('Alice', 'Smith', 'alice@example.com'),
('Bob', 'Johnson', 'bob@example.com'),
('Charlie', 'Brown', 'charlie@example.com'),
('Diana', 'Ross', 'diana@example.com');

-- Insert sample Products
INSERT INTO products (name, description, price, stock) VALUES
('Laptop', 'High performance laptop', 1200.00, 10),
('Mouse', 'Wireless ergonomic mouse', 25.50, 50),
('Keyboard', 'Mechanical gaming keyboard', 75.00, 30),
('Monitor', '27-inch 4K monitor', 400.00, 15),
('Headphones', 'Noise cancelling headphones', 150.00, 25);

-- Insert sample Orders
INSERT INTO orders (user_id, status) VALUES
(1, 'completed'),
(1, 'pending'),
(2, 'completed'),
(3, 'shipped'),
(4, 'completed'),
(5, 'pending');

-- Insert sample Order Items
INSERT INTO order_items (order_id, product_id, quantity, price) VALUES
(1, 1, 1, 1200.00),
(1, 2, 2, 25.50),
(2, 3, 1, 75.00),
(3, 4, 1, 400.00),
(3, 5, 1, 150.00),
(4, 2, 3, 25.50),
(5, 1, 1, 1200.00),
(5, 5, 2, 150.00),
(6, 3, 1, 75.00);
