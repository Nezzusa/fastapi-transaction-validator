from fastapi import FastAPI
from pydantic import BaseModel

class PaymentInput(BaseModel):
    amount: float
    currency: str
    sender: str
    receiver: str

app = FastAPI()


#receives payment
@app.post("/api/payment")
async def process_payment(payment: PaymentInput):
    print(f"Received payment from {payment.sender} of {payment.amount} {payment.currency}")




    return {"status": "success", "received_amount": payment.amount}
