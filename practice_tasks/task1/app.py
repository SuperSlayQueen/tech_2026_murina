from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from datetime import datetime

DATABASE_URL = "postgresql://user:password@db:5432/store"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# модели
class Customer(Base):
    __tablename__ = "customers"
    CustomerID = Column(Integer, primary_key=True)
    FirstName = Column(String)
    LastName = Column(String)
    Email = Column(String)

class Product(Base):
    __tablename__ = "products"
    ProductID = Column(Integer, primary_key=True)
    ProductName = Column(String)
    Price = Column(Float)

class Order(Base):
    __tablename__ = "orders"
    OrderID = Column(Integer, primary_key=True)
    CustomerID = Column(Integer, ForeignKey("customers.CustomerID"))
    OrderDate = Column(DateTime, default=datetime.utcnow)
    TotalAmount = Column(Float, default=0)

class OrderItem(Base):
    __tablename__ = "orderitems"
    OrderItemID = Column(Integer, primary_key=True)
    OrderID = Column(Integer, ForeignKey("orders.OrderID"))
    ProductID = Column(Integer, ForeignKey("products.ProductID"))
    Quantity = Column(Integer)
    Subtotal = Column(Float)

# создаём таблицы
Base.metadata.create_all(bind=engine)

# сценарий 1
def create_order(customer_id, items):
    session = SessionLocal()
    try:
        order = Order(CustomerID=customer_id)
        session.add(order)
        session.flush()

        total = 0

        for product_id, qty in items:
            product = session.query(Product).filter_by(ProductID=product_id).one()
            subtotal = product.Price * qty

            session.add(OrderItem(
                OrderID=order.OrderID,
                ProductID=product_id,
                Quantity=qty,
                Subtotal=subtotal
            ))

            total += subtotal

        order.TotalAmount = total
        session.commit()
        print("Order created")

    except Exception as e:
        session.rollback()
        print("Error:", e)
    finally:
        session.close()

# сценарий 2
def update_email(customer_id, new_email):
    session = SessionLocal()
    try:
        customer = session.query(Customer).filter_by(CustomerID=customer_id).one()
        customer.Email = new_email

        session.commit()
        print("Email updated")

    except Exception as e:
        session.rollback()
        print("Error:", e)
    finally:
        session.close()

# сценарий 3
def add_product(name, price):
    session = SessionLocal()
    try:
        session.add(Product(ProductName=name, Price=price))
        session.commit()
        print("Product added")

    except Exception as e:
        session.rollback()
        print("Error:", e)
    finally:
        session.close()

# тест
if __name__ == "__main__":
    add_product("Phone", 500)