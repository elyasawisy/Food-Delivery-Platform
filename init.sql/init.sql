
-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    role VARCHAR(20) NOT NULL,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Restaurants table
CREATE TABLE IF NOT EXISTS restaurants (
    id SERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    address VARCHAR(255),
    phone VARCHAR(20)
);

-- Menu Items table
CREATE TABLE IF NOT EXISTS menu_items (
    id SERIAL PRIMARY KEY,
    restaurant_id INTEGER REFERENCES restaurants(id) ON DELETE CASCADE,
    name VARCHAR(120) NOT NULL,
    price FLOAT NOT NULL,
    image_url VARCHAR(255)
);

-- Orders table
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES users(id),
    restaurant_id INTEGER REFERENCES restaurants(id),
    driver_id INTEGER REFERENCES users(id),
    status VARCHAR(20) DEFAULT 'confirmed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Order Items table
CREATE TABLE IF NOT EXISTS order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
    menu_item_id INTEGER REFERENCES menu_items(id),
    quantity INTEGER NOT NULL DEFAULT 1
);

-- Payments table
CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
    amount FLOAT NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Customer Support Chat table
CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    sender_id INTEGER REFERENCES users(id),
    receiver_id INTEGER REFERENCES users(id),
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    delivered BOOLEAN DEFAULT FALSE
);

-- Image Upload Jobs table
CREATE TABLE IF NOT EXISTS image_upload_jobs (
    id SERIAL PRIMARY KEY,
    restaurant_id INTEGER REFERENCES restaurants(id),
    filename VARCHAR(255) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);


-- Indexes for better performance
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_chat_messages_sender ON chat_messages(sender_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_receiver ON chat_messages(receiver_id);



-- Insert test data
INSERT INTO users (role, name, email, password_hash, phone) VALUES
('customer', 'John Doe', 'john@example.com', 'hash1', '555-1001'),
('customer', 'Jane Smith', 'jane@example.com', 'hash2', '555-1002'),
('customer', 'Bob Wilson', 'bob@example.com', 'hash3', '555-1003'),
('driver', 'Mike Driver', 'mike@example.com', 'hash4', '555-1004'),
('driver', 'Sarah Delivery', 'sarah@example.com', 'hash5', '555-1005'),
('restaurant_owner', 'Pizza Owner', 'owner@pizza.com', 'hash6', '555-1006');

INSERT INTO restaurants (name, address, phone) VALUES
('Pizza Palace', '123 Main St', '555-2001'),
('Burger Barn', '456 Oak Ave', '555-2002'),
('Sushi Central', '789 Pine St', '555-2003'),
('Taco Town', '321 Elm St', '555-2004');

INSERT INTO menu_items (restaurant_id, name, price) VALUES
-- Pizza Palace menu
(1, 'Margherita Pizza', 12.99),
(1, 'Pepperoni Pizza', 14.99),
(1, 'Supreme Pizza', 17.99),
(1, 'Garlic Bread', 6.99),
-- Burger Barn menu
(2, 'Classic Burger', 8.99),
(2, 'Cheese Burger', 9.99),
(2, 'Bacon Burger', 11.99),
(2, 'Fries', 4.99),
-- Sushi Central menu
(3, 'Salmon Roll', 7.99),
(3, 'Tuna Roll', 6.99),
(3, 'California Roll', 8.99),
(3, 'Miso Soup', 3.99),
-- Taco Town menu
(4, 'Beef Taco', 3.99),
(4, 'Chicken Taco', 4.49),
(4, 'Fish Taco', 5.99),
(4, 'Guacamole', 2.99);

-- Orders without total_amount
INSERT INTO orders (customer_id, restaurant_id, status, created_at) VALUES
(1, 1, 'delivered', NOW() - INTERVAL '2 hours'),
(2, 2, 'picked_up', NOW() - INTERVAL '1 hour'),
(3, 3, 'preparing', NOW() - INTERVAL '30 minutes'),
(1, 4, 'confirmed', NOW() - INTERVAL '10 minutes');

-- Order items without price
INSERT INTO order_items (order_id, menu_item_id, quantity) VALUES
(1, 1, 2),
(1, 4, 1),
(2, 5, 2),
(2, 8, 1),
(3, 9, 2),
(3, 12, 1),
(4, 13, 3),
(4, 16, 1);

