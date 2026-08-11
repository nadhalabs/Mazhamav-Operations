from sqlalchemy import select
from app.core.config import get_settings
from app.core.security import hash_password
from app.database import SessionLocal
from app.models import Product, User, UserRole


def seed_development():
    settings = get_settings()
    if settings.environment != "development":
        raise RuntimeError("Development seed is disabled outside development")
    with SessionLocal() as db:
        if not db.scalar(select(User).where(User.role == UserRole.owner)):
            db.add(User(full_name="Mazha Mav Owner", phone=settings.seed_owner_phone, password_hash=hash_password(settings.seed_owner_password), role=UserRole.owner))
        samples = [("Mazha Mav Classic", "MM-CLASSIC", "packet", 120), ("Mazha Mav Family Pack", "MM-FAMILY", "packet", 220), ("Mazha Mav Mini", "MM-MINI", "packet", 60)]
        existing = set(db.scalars(select(Product.sku)).all())
        db.add_all([Product(name=n, sku=s, unit_name=u, selling_price=p) for n, s, u, p in samples if s not in existing])
        db.commit()


if __name__ == "__main__":
    seed_development()

