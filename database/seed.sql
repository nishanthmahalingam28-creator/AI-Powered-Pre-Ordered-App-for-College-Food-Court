USE food_court_db;

-- 1. Insert Admin and Vendors
INSERT INTO users (id, email, password_hash, role, is_active) VALUES
(1, 'admin@kpriet.ac.in', '$2b$12$javr8isyS09IuKhtfYcWaOagdgD4a6np/bEC2TNro/.W46emPpZ..', 'admin', 1),
(2, 'ypr@kpriet.ac.in', '$2b$12$7GBWTk0Rcnao/BtXOmfCEuYCWDSjd2JyIx9UTLS7NIJRDw6.nnJLO', 'vendor', 1),
(3, 'campus@kpriet.ac.in', '$2b$12$7GBWTk0Rcnao/BtXOmfCEuYCWDSjd2JyIx9UTLS7NIJRDw6.nnJLO', 'vendor', 1),
(4, 'german@kpriet.ac.in', '$2b$12$7GBWTk0Rcnao/BtXOmfCEuYCWDSjd2JyIx9UTLS7NIJRDw6.nnJLO', 'vendor', 1),
(5, 'royal@kpriet.ac.in', '$2b$12$7GBWTk0Rcnao/BtXOmfCEuYCWDSjd2JyIx9UTLS7NIJRDw6.nnJLO', 'vendor', 1),
(6, 'mario@kpriet.ac.in', '$2b$12$7GBWTk0Rcnao/BtXOmfCEuYCWDSjd2JyIx9UTLS7NIJRDw6.nnJLO', 'vendor', 1),
(7, 'saaral@kpriet.ac.in', '$2b$12$7GBWTk0Rcnao/BtXOmfCEuYCWDSjd2JyIx9UTLS7NIJRDw6.nnJLO', 'vendor', 1),
(8, 'student@kpriet.ac.in', '$2b$12$RNoQnQ6JWRAf5zK4zYjS8.2hbfSMnt1bQJrVJK7d7EGTR4jeiKNdC', 'customer', 1)
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
-- YPR (Offerings: Food)
(1, 1, 'Crispy Ghee Podi Dosa', 'Golden crispy dosa roasted in pure ghee and spiced podi with coconut chutney', 65.00, 'Food', 30, 1),
(2, 1, 'Special South Indian Meals', 'Steamed rice, sambar, rasam, kootu, poriyal, curd, and appalam', 90.00, 'Food', 25, 1),
(3, 1, 'Egg Parotta (2 Pcs)', 'Layered flaky parotta served with rich salna and onion raita', 70.00, 'Food', 20, 1),

-- Campus Kitchen (Dev Seed Stall)
(4, 2, 'Paneer Butter Masala Combo', 'Rich paneer gravy served with 3 butter rotis and jeera rice', 110.00, 'Food', 25, 1),
(5, 2, 'Dal Makhani Rice Bowl', 'Slow-cooked black lentils in creamy butter sauce over fragrant basmati', 85.00, 'Food', 20, 1),
(6, 2, 'Aloo Paratha with Curd', 'Stuffed spiced potato paratha served with fresh curd and pickle', 55.00, 'Food', 35, 1),

-- German Cafe (Offerings: Food)
(7, 3, 'Crispy Veg Supreme Burger', 'Herbed potato-corn patty with melted cheese, lettuce, and secret sauce', 75.00, 'Food', 20, 1),
(8, 3, 'Peri Peri Loaded Fries', 'Golden french fries seasoned with spicy peri-peri dust and cheese mayo', 60.00, 'Food', 40, 1),
(9, 3, 'Grilled Chicken Sandwich', 'Toasted triple-layer sandwich with shredded chicken, mayo, and herbs', 90.00, 'Food', 15, 1),

-- Royal Kitchen (Offerings: Food, Tea, Snacks)
(10, 4, 'Royal Chicken Dum Biryani', 'Aromatic seeraga samba rice cooked with tender chicken pieces and spices', 140.00, 'Food', 35, 1),
(11, 4, 'Schezwan Veg Fried Rice', 'Wok-tossed basmati rice with crunchy vegetables in spicy schezwan sauce', 90.00, 'Food', 25, 1),
(12, 4, 'Royal Masala Chai', 'Aromatic spiced milk tea brewed with crushed cardamom and ginger', 20.00, 'Tea', 50, 1),
(13, 4, 'Crispy Chicken Cutlet', 'Crisp spiced chicken patty served with mint chutney', 50.00, 'Snacks', 25, 1),

-- Mario (Offerings: Juice, Maggi)
(14, 5, 'Fresh Mango Alphonso Shake', 'Thick chilled shake made with ripe Alphonso mangoes and vanilla ice cream', 60.00, 'Juice', 25, 1),
(15, 5, 'Fresh Sweet Lime Juice', 'Freshly pressed sweet lime citrus cooler with mint sprig', 45.00, 'Juice', 30, 1),
(16, 5, 'Classic Veg Masala Maggi', 'Wok-tossed noodles with diced vegetables and authentic tastemaker masala', 40.00, 'Maggi', 35, 1),
(17, 5, 'Cheese Butter Maggi', 'Double spiced Maggi topped with melted butter and generous grated cheese', 55.00, 'Maggi', 25, 1),

-- Saaral (Offerings: Snacks, Cakes)
(18, 6, 'Hot Samosa (2 Pcs) & Chutney', 'Crisp triangular pastry stuffed with spiced potato and peas', 30.00, 'Snacks', 45, 1),
(19, 6, 'Crispy Onion Pakoda', 'Deep fried crunchy onion fritters with green chili and curry leaves', 35.00, 'Snacks', 40, 1),
(20, 6, 'Chocolate Truffle Cake Slice', 'Rich moist dark chocolate sponge layered with Dutch chocolate ganache', 65.00, 'Cakes', 20, 1),
(21, 6, 'Red Velvet Cupcake', 'Velvety crimson sponge topped with vanilla cream cheese frosting', 45.00, 'Cakes', 25, 1)
ON DUPLICATE KEY UPDATE name=VALUES(name), price=VALUES(price), quantity=VALUES(quantity), category=VALUES(category);
