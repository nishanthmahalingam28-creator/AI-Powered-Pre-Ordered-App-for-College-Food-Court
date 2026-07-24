# 🍽️ SmartCampus AI
### AI-Powered College Food Court Management System

## 📖 Overview

SmartCampus AI is a mobile application designed to improve the food ordering experience in college food courts. The system allows students to pre-order food, pay online, receive a secure OTP for pickup, and collect their orders without waiting in long queues.

The application also helps food vendors manage orders efficiently while using Artificial Intelligence (AI) to predict customer demand and reduce food waste.

This project is being developed for the **Campus Innovation Challenge 2026**.

---

# 🎯 Problem Statement

Students often spend a significant amount of time waiting in queues at the college food court during break and lunch hours.

Current challenges include:
- Long waiting times
- Food shortages during peak hours
- Food wastage due to inaccurate preparation
- No centralized ordering system
- Manual order handling
- Difficulty managing multiple food outlets

---

# 💡 Proposed Solution

Develop an AI-powered mobile application where students can:

- Login using their College ID
- Browse food menus from different shops
- Place food orders in advance
- Pay online
- Receive a digital bill
- Get a randomly generated OTP for secure food pickup
- Track order status in real time

Food vendors receive orders instantly and prepare food before the student arrives.

---

# 🏪 Food Court Shops

The application supports the following food outlets:

1. Saral
   - Snacks
   - Cakes

2. Royal Kitchen
   - Food
   - Snacks
     
3. Mario
   - Juice
   - Food

4. YPR
   - Food

5. German Cafe
   - Food

---

# ✨ Features

## Student

- College Login
- Browse Shops
- View Menu
- Search Food Items
- Add to Cart
- Online Payment
- Digital Bill
- Random OTP Generation
- Order Tracking
- Order History
- Notifications

---

## Vendor

- Vendor Login
- View Incoming Orders
- Accept / Reject Orders
- Update Order Status
- Verify Student OTP
- Complete Orders
- Daily Sales Report

---

## Admin

- Manage Students
- Manage Shops
- Manage Food Menu
- Manage Vendors
- View Payments
- View Reports
- Analytics Dashboard

---

# 🤖 AI Features

- Food Recommendation System
- Demand Prediction
- Queue Waiting Time Prediction
- Peak Hour Prediction
- Food Waste Prediction

---

# 🔐 Secure Order Pickup

After successful payment:

1. Order ID is generated.
2. Random 6-digit OTP is generated.
3. Student receives a digital bill.
4. Vendor receives the same OTP.
5. Student provides Order ID and OTP during pickup.
6. Vendor verifies the OTP.
7. Food is delivered.

---

# 🏗️ System Architecture

Student Mobile App
        │
        ▼
Django REST API
        │
        ▼
MySQL Database
        │
        ▼
Vendor Dashboard
        │
        ▼
Admin Dashboard
        │
        ▼
AI Prediction Module

---

# 🛠️ Technology Stack

## Frontend
- Flutter

## Backend
- Python
- Django
- Django REST Framework

## Database
- MySQL

## AI / ML
- Pandas
- NumPy
- Scikit-learn

## Data Visualization
- Matplotlib
- Plotly

## Payment Gateway
- Razorpay (Test Mode)

## Version Control
- Git
- GitHub

---

# 📂 Project Structure

```
SmartCampusAI/
│
├── mobile_app/
├── backend/
├── database/
├── ai/
├── docs/
├── presentation/
├── assets/
├── screenshots/
└── README.md
```

---

# 👥 Team Members

| Role | Responsibility |
|------|----------------|
| Member 1 | Project Management & GitHub |
| Member 2 | Flutter UI Development |
| Member 3 | Flutter App Development |
| Member 4 | Django Backend |
| Member 5 | Database & API Integration |
| Member 6 | AI/ML Development |

---

# 🚀 Future Enhancements

- Voice-based food ordering
- Smart chatbot
- Loyalty reward points
- Personalized meal recommendations
- Nutrition information
- Push notifications
- Multi-campus support

---

# 🎯 Project Goal

Our goal is to build an intelligent food court management system that:

- Reduces student waiting time
- Improves food ordering efficiency
- Helps vendors manage orders
- Predicts customer demand using AI
- Minimizes food wastage
- Provides a seamless digital food ordering experience

---

# 📄 License

This project is developed for educational purposes as part of the Campus Innovation Challenge 2026.

---

## ⭐ SmartCampus AI
### Order Smart • Eat Faster • Reduce Food Waste
