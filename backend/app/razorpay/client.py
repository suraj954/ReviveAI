import razorpay

from app.config import settings


client = razorpay.Client(
    auth=(
        settings.razorpay_key_id,
        settings.razorpay_key_secret,
    )
)


client.set_app_details(
    {
        "title": settings.app_name,
        "version": "0.1.0",
    }
)