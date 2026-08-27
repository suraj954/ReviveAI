from app.config import settings


def main() -> None:
    print("Configuration loaded successfully.")
    print(f"Application: {settings.app_name}")
    print(f"Environment: {settings.app_env}")

    # Never print secret values.
    print(
        "Razorpay Key ID loaded:",
        bool(settings.razorpay_key_id),
    )

    print(
        "Razorpay API Secret loaded:",
        bool(settings.razorpay_key_secret),
    )

    print(
        "Razorpay Webhook Secret loaded:",
        bool(settings.razorpay_webhook_secret),
    )


if __name__ == "__main__":
    main()