USE food_court_db;

-- 1. Insert Admin and Vendors
INSERT INTO users (id, email, password_hash, role, is_active) VALUES
(1, 'admin@kpriet.ac.in', 'scrypt:32768:8:1$kDMEgRswIGIMkuqc$eab9396a7b7cdb2a3d122c7e9e46899c3e31f1437e93be11debc5f8d52a5daa9e5a1b708c0dba5f9e6d84389573e87bfe6b3672e9e7c127f7325b8e732796bbd', 'admin', 1),
(2, 'ypr@kpriet.ac.in', 'scrypt:32768:8:1$JvyIhZiPzUYhvRQI$477e278bbbf597f48a4a13c4af78a4b229fcbddcb6b7c8560e5208350a5ba38378727a7374b42b818a653ca0afd7eac3e0951bb0b5dfe4bacf1fc970d57ab812', 'vendor', 1),
(3, 'campus@kpriet.ac.in', 'scrypt:32768:8:1$JvyIhZiPzUYhvRQI$477e278bbbf597f48a4a13c4af78a4b229fcbddcb6b7c8560e5208350a5ba38378727a7374b42b818a653ca0afd7eac3e0951bb0b5dfe4bacf1fc970d57ab812', 'vendor', 1),
(4, 'german@kpriet.ac.in', 'scrypt:32768:8:1$JvyIhZiPzUYhvRQI$477e278bbbf597f48a4a13c4af78a4b229fcbddcb6b7c8560e5208350a5ba38378727a7374b42b818a653ca0afd7eac3e0951bb0b5dfe4bacf1fc970d57ab812', 'vendor', 1),
(5, 'royal@kpriet.ac.in', 'scrypt:32768:8:1$JvyIhZiPzUYhvRQI$477e278bbbf597f48a4a13c4af78a4b229fcbddcb6b7c8560e5208350a5ba38378727a7374b42b818a653ca0afd7eac3e0951bb0b5dfe4bacf1fc970d57ab812', 'vendor', 1),
(6, 'mario@kpriet.ac.in', 'scrypt:32768:8:1$JvyIhZiPzUYhvRQI$477e278bbbf597f48a4a13c4af78a4b229fcbddcb6b7c8560e5208350a5ba38378727a7374b42b818a653ca0afd7eac3e0951bb0b5dfe4bacf1fc970d57ab812', 'vendor', 1),
(7, 'saaral@kpriet.ac.in', 'scrypt:32768:8:1$JvyIhZiPzUYhvRQI$477e278bbbf597f48a4a13c4af78a4b229fcbddcb6b7c8560e5208350a5ba38378727a7374b42b818a653ca0afd7eac3e0951bb0b5dfe4bacf1fc970d57ab812', 'vendor', 1),
(8, 'student@kpriet.ac.in', 'scrypt:32768:8:1$DNYeAwHNQA8pkCvz$b644ddf580be342c8499751b264076f8e38edd8c0fdea8dabb51413c3d93c8650747cf831919c828082bf67c30f56f484132c0e2591decc6a065a19fd38e02f8', 'customer', 1)
ON DUPLICATE KEY UPDATE password_hash=VALUES(password_hash), role=VALUES(role);

-- 2. Customer profile for sample student
INSERT INTO customer_profiles (user_id, customer_type, full_name, identifier, mobile) VALUES
(8, 'student', 'KPR Student', '21CS042', '9876543210')
ON DUPLICATE KEY UPDATE full_name=VALUES(full_name);

-- 3. Insert Food Court Stalls
INSERT INTO shops (id, name, slug, owner_user_id, description, category, is_active) VALUES
(1, 'YPR', 'ypr', 2, 'Fresh authentic South Indian hot meals, dosas, and parottas', 'South Indian', 1),
(2, 'Campus Kitchen', 'campus-kitchen', 3, 'Homestyle healthy combo meals, curries, and rotis', 'North & South', 1),
(3, 'German Cafe', 'german-cafe', 4, 'Crispy burgers, cheesy sandwiches, fries, and cold brews', 'Fast Food', 1),
(4, 'Royal Kitchen', 'royal-kitchen', 5, 'Special Biryanis, fried rice, noodles, and chicken delights', 'Biryani & Chinese', 1),
(5, 'Mario', 'mario', 6, 'Fresh fruit juices, shakes, smoothies, and quick pastries', 'Beverages & Juices', 1),
(6, 'Saaral', 'saaral', 7, 'Traditional snacks, tea, filter coffee, samosas, and evening bites', 'Snacks & Cafe', 1)
ON DUPLICATE KEY UPDATE name=VALUES(name), description=VALUES(description);

-- 4. Insert Initial Menu Items
INSERT INTO menu_items (id, shop_id, name, description, price, category, quantity, is_available) VALUES
-- YPR
(1, 1, 'Crispy Ghee Podi Dosa', 'Golden crispy dosa roasted in pure ghee and spiced podi with coconut chutney', 65.00, 'Main Course', 30, 1),
(2, 1, 'Special South Indian Meals', 'Steamed rice, sambar, rasam, kootu, poriyal, curd, and appalam', 90.00, 'Main Course', 25, 1),
(3, 1, 'Egg Parotta (2 Pcs)', 'Layered flaky parotta served with rich salna and onion raita', 70.00, 'Main Course', 20, 1),

-- Campus Kitchen
(4, 2, 'Paneer Butter Masala Combo', 'Rich paneer gravy served with 3 butter rotis and jeera rice', 110.00, 'Main Course', 25, 1),
(5, 2, 'Dal Makhani Rice Bowl', 'Slow-cooked black lentils in creamy butter sauce over fragrant basmati', 85.00, 'Main Course', 20, 1),
(6, 2, 'Aloo Paratha with Curd', 'Stuffed spiced potato paratha served with fresh curd and pickle', 55.00, 'Breakfast', 35, 1),

-- German Cafe
(7, 3, 'Crispy Veg Supreme Burger', 'Herbed potato-corn patty with melted cheese, lettuce, and secret sauce', 75.00, 'Fast Food', 20, 1),
(8, 3, 'Peri Peri Loaded Fries', 'Golden french fries seasoned with spicy peri-peri dust and cheese mayo', 60.00, 'Snacks', 40, 1),
(9, 3, 'Grilled Chicken Sandwich', 'Toasted triple-layer sandwich with shredded chicken, mayo, and herbs', 90.00, 'Fast Food', 15, 1),

-- Royal Kitchen
(10, 4, 'Royal Chicken Dum Biryani', 'Aromatic seeraga samba rice cooked with tender chicken pieces and spices', 140.00, 'Main Course', 35, 1),
(11, 4, 'Schezwan Veg Fried Rice', 'Wok-tossed basmati rice with crunchy vegetables in spicy schezwan sauce', 90.00, 'Chinese', 25, 1),
(12, 4, 'Chicken Noodles', 'Hakka noodles tossed with egg, shredded chicken, and spring onions', 110.00, 'Chinese', 20, 1),

-- Mario
(13, 5, 'Fresh Mango Alphonso Shake', 'Thick chilled shake made with ripe Alphonso mangoes and vanilla ice cream', 60.00, 'Beverages', 25, 1),
(14, 5, 'Cold Coffee with Cream', 'Blended robust espresso with cold milk and whipped cream crown', 50.00, 'Beverages', 30, 1),
(15, 5, 'Chocolate Lava Pastry', 'Warm gooey molten chocolate cake dusted with powdered sugar', 55.00, 'Desserts', 15, 1),

-- Saaral
(16, 6, 'Filter Coffee (Special Degree)', 'Freshly brewed Kumbakonam style decoction milk coffee', 25.00, 'Beverages', 50, 1),
(17, 6, 'Hot Samosa (2 Pcs) & Chutney', 'Crisp triangular pastry stuffed with spiced potato and peas', 30.00, 'Snacks', 45, 1),
(18, 6, 'Masala Tea', 'Strong hand-brewed ginger cardamom milk tea', 20.00, 'Beverages', 60, 1)
ON DUPLICATE KEY UPDATE name=VALUES(name), price=VALUES(price), quantity=VALUES(quantity);
