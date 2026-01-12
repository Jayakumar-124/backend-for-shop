from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import List, Optional
import uvicorn
import mysql.connector
from mysql.connector import errorcode
from datetime import datetime
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env

app = FastAPI(title="Hesha Premium API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Database Setup ---
import os

DB_CONFIG = {
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'host': os.getenv('DB_HOST', '127.0.0.1'),
    'database': os.getenv('DB_NAME', 'hesha_food_db'),
    'port': int(os.getenv('DB_PORT', 3306))
}

def init_db():
    try:
        # On local (XAMPP), we might need to create the DB first
        # On Cloud DBs, the DB is usually pre-created or we don't have permission to create one
        if DB_CONFIG['host'] == '127.0.0.1' or DB_CONFIG['host'] == 'localhost':
            conn = mysql.connector.connect(
                user=DB_CONFIG['user'], 
                password=DB_CONFIG['password'], 
                host=DB_CONFIG['host'],
                port=DB_CONFIG['port']
            )
            cursor = conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']}")
            conn.close()

        # Connect to the specific database
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Table creation logic remains the same
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                address LONGTEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id VARCHAR(50) PRIMARY KEY,
                user_id INT,
                total DECIMAL(10, 2),
                status VARCHAR(50),
                items LONGTEXT,
                address LONGTEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                price DECIMAL(10, 2),
                img VARCHAR(255),
                category VARCHAR(100)
            )
        ''')
        
        conn.commit()
        conn.close()
        print(f"✅ Database & Tables initialized successfully on {DB_CONFIG['host']}!")
    except mysql.connector.Error as err:
        print(f"❌ Database Initialization Warning/Error: {err}")

# Only try to init if we aren't in a "read-only" environment or just run it and catch
init_db()

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

# --- Pydantic Models ---
class UserSignup(BaseModel):
    name: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class AddressUpdate(BaseModel):
    user_id: int
    addresses: List[dict]

class Address(BaseModel):
    fullname: str
    street: str
    city: str
    zip: str
    phone: str

class OrderItem(BaseModel):
    title: str
    price: float
    img: str
    quantity: int

class OrderCreate(BaseModel):
    user_id: Optional[int] = None
    items: List[OrderItem]
    total: float
    address: Address

# --- Email Helper ---
def send_order_notification(order_id: str, total: float, items: list, address: dict):
    sender_email = os.getenv('SENDER_EMAIL', 'jayakumarkathiraven@gmail.com')
    sender_password = os.getenv('SENDER_PASSWORD', '') 
    receiver_email = os.getenv('RECEIVER_EMAIL', 'jayakumarkathiraven@gmail.com')
    
    if not sender_password:
        print(f"⚠️ Email notification skipped: SENDER_PASSWORD not set. Order #{order_id} recorded in DB.")
        return

    subject = f"NEW ORDER CONFIRMED - #{order_id}"
    
    # Format items for the email
    items_list = ""
    for item in items:
        items_list += f"- {item['title']} (x{item['quantity']}) - ₹{item['price'] * item['quantity']}\n"
    
    body = f"""
    New Order Received!
    
    Order ID: {order_id}
    Total Amount: ₹{total:.2f}
    Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    
    --- Customer Information ---
    Name: {address['fullname']}
    Phone: {address['phone']}
    Address: {address['street']}, {address['city']} - {address['zip']}
    
    --- Order Items ---
    {items_list}
    
    Please process this order for delivery.
    """
    
    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        print(f"📧 Notification email sent for Order #{order_id}")
    except Exception as e:
        print(f"❌ Failed to send order notification: {e}")


# --- API Routes ---

@app.post("/api/signup")
async def signup(user: UserSignup):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)", 
                       (user.name, user.email, user.password))
        conn.commit()
        user_id = cursor.lastrowid
        return {"id": user_id, "name": user.name, "email": user.email, "message": "User created successfully"}
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_DUP_ENTRY:
             raise HTTPException(status_code=400, detail="Email already registered")
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        conn.close()

@app.post("/api/login")
async def login(user: UserLogin):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name, email, password, address FROM users WHERE email = %s", (user.email,))
    row = cursor.fetchone()
    conn.close()
    
    if row and row['password'] == user.password:
        address_data = json.loads(row['address']) if row['address'] else None
        return {
            "id": row['id'],
            "name": row['name'],
            "email": row['email'],
            "address": address_data,
            "isLoggedIn": True
        }
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/api/products")
async def get_products():
    return [
        {"id": 1, "title": "Idli & Dosa Batter", "price": 120.00, "img": "JPG/Front.jpeg", "category": "Batter"},
        {"id": 2, "title": "Crispy Golden Dosa", "price": 150.00, "img": "dosa.png", "category": "Breakfast"},
        {"id": 3, "title": "Lacy Appam", "price": 80.00, "img": "rava_idli.png", "category": "Specialties"},
    ]

@app.post("/api/orders")
async def create_order(order: OrderCreate):
    order_id = f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}"
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        items_json = json.dumps([item.dict() for item in order.items])
        address_json = json.dumps(order.address.dict())
        
        cursor.execute('''
            INSERT INTO orders (id, user_id, total, status, items, address)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (order_id, order.user_id, order.total, "Delivered", items_json, address_json))
        
        if order.user_id:
            cursor.execute("UPDATE users SET address = %s WHERE id = %s", (address_json, order.user_id))
            
        conn.commit()
        
        # Send notification email to heshafoods@gmail.com
        send_order_notification(
            order_id=order_id, 
            total=order.total, 
            items=[item.dict() for item in order.items], 
            address=order.address.dict()
        )
        
        return {"id": order_id, "message": "Order placed successfully"}
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        conn.close()

@app.get("/api/orders/{user_id}")
async def get_user_orders(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, total, status, items, address, created_at FROM orders WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    orders = []
    for row in rows:
        orders.append({
            "id": row['id'],
            "total": float(row['total']),
            "status": row['status'],
            "items": json.loads(row['items']),
            "address": json.loads(row['address']),
            "date": row['created_at'].isoformat()
        })
    return orders

@app.post("/api/user/address")
async def update_user_address(data: AddressUpdate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        address_json = json.dumps(data.addresses)
        cursor.execute("UPDATE users SET address = %s WHERE id = %s", (address_json, data.user_id))
        conn.commit()
        return {"message": "Addresses updated successfully"}
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        conn.close()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
