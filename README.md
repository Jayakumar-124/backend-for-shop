# Batter-Shop
# Hesha Premium Backend 🚀

This is a FastAPI-based backend for the Hesha Premium Food application.

## 🛠️ Setup Instructions

1. **Python Version**: Ensure you have Python 3.8+ installed.
2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Run the Server**:
   ```bash
   python main.py
   ```
   The server will start at `http://127.0.0.1:8000`.

## 📌 API Endpoints

- **POST `/api/signup`**: Register a new user.
- **POST `/api/login`**: Authenticate and get user details.
- **GET `/api/products`**: Fetch the list of available products.
- **POST `/api/orders`**: Create a new order (saves to database).
- **GET `/api/orders/{user_id}`**: Retrieve order history for a specific user.

## 🗄️ Database
The application uses **SQLite** (`heshe_food.db`). The tables are automatically created on the first run.

## 🔗 Connecting to Frontend
Update your frontend fetch calls to point to `http://127.0.0.1:8000`. Ensure CORS is handled (it is enabled by default in `main.py`).
