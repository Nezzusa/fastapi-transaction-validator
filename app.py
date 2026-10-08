from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import create_engine



class PaymentInput(BaseModel):
    amount: float
    currency: str
    sender: str
    receiver: str

app = FastAPI()
db_engine = create_engine("sqlite:///paymentprocessing.db",
                               connect_args={"check_same_thread": False})

with db_engine.connect() as conn:
    conn.execute() # initialize database

    conn.commit()


#receives payment
@app.post("/api/payment")
async def process_payment(payment: PaymentInput):
    print(f"Received payment from {payment.sender} of {payment.amount} {payment.currency}")


    #place for database connection
    with db_engine.connect() as conn:


    return {"status": "success", "received_amount": payment.amount}
