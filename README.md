FRUITHUB
Fresh. Local. Within 5 KM.

A premium 3D marketplace for fruits, juices and dry fruits. Customers order from stores within 5 km. Store owners manage products, stock, offers and orders. An admin approves stores and oversees the platform.

NOTE: Generated from project conversation notes, not from the repository. Commands and paths marked (confirm) have not been checked against the code.


FEATURES

Customers
- Register and verify mobile number by OTP (test mode: the code prints in the backend terminal).
- Pick a delivery location on the map: a 5 km check runs against the store's location.
- Browse Fruits, Juices and Dry fruits with search, filters and sorting.
- Products with sizes (variants such as 250 g or 500 ml), each with its own price and stock.
- Cart and checkout. Customers outside a seller's delivery area can still check out; delivery is arranged and paid separately.
- Pay by UPI: open the payment link, submit the transaction reference. The order is paid only after the owner verifies the money arrived.
- Order tracking: PACKING, READY, OUT FOR DELIVERY, DELIVERED.
- Reviews, after delivery only.

Store owners
- Save's  UPI ID for payments.
- Handle products, variants, stock (with history), images and offers.
- Verify or reject UPI payments; manage orders through each status.
- Store settings: delivery radius, FSSAI number.

Admin
- Create owners, approve stores (FSSAI number required), manage categories, products, orders, offers, users.
- Analytics.

Food information
- Ingredients, allergens, veg mark, shelf life, storage note, made-to-order (fresh juices), no-added-sugar flag, nutrition.


PAYMENTS

Direct UPI, not an online gateway, for now.
- A submitted reference reserves stock for 24 hours.
- An unverified order expires after 24 hours and its stock is restored.
- A submitted reference is not proof of payment.
- Refunds are manual. The app does not refund direct UPI payments automatically.
- Razorpay (signature checks, webhooks, refunds) is planned for launch.


TECH STACK

Backend: Python 3.13, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, JWT, Argon2.
Frontend: plain HTML, CSS and JavaScript modules, Three.js (3D), Leaflet with OpenStreetMap (maps, planned).
Mobile: planned Android app on the same REST API.


PROJECT LAYOUT (confirm)

fruithub/
  backend/
    app/            FastAPI application (main.py, services/, models, schemas)
    alembic/        database migrations
    tests/          pytest tests
  frontend/         HTML, CSS and JavaScript pages
Virtual environment: one folder above fruithub, at ..\.venv


SETUP (Windows, PowerShell; confirm)

1. Start PostgreSQL on port 5433.
2. Back up the database before any migration.
3. Activate the virtual environment:
   C:\Users\HP\OneDrive\Attachments\app\.venv\Scripts\Activate.ps1
4. Go to the backend folder:
   cd C:\Users\HP\OneDrive\Attachments\app\fruithub\backend
5. Set environment variables in .env (never commit it). Include the database URL, SECRET_KEY and OTP_DEV_MODE=true for testing.
6. Apply migrations:
   alembic current
   alembic heads          (must show one head)
   alembic upgrade head
   alembic current
7. Start the backend:
   uvicorn app.main:app --reload        (http://127.0.0.1:8000)
8. API docs: http://localhost:8000/docs
9. Start the frontend with VS Code Live Server on port 5500.


TESTING

Backend tests:    python -m pytest -q          (last recorded run: 84 passed)
Frontend:         JavaScript syntax checks     (last recorded run: passed)
Migrations:       alembic upgrade head renders offline without errors (last recorded run)

Not yet verified: the full acceptance test (see below) and the expiry job against the real database.


ACCEPTANCE TEST

1. Start PostgreSQL, backend and frontend.
2. Register a customer, verify OTP, log in.
3. Pick a delivery location; the 5 km check runs.
4. Browse Fruits, Juices and Dry fruits; see the animated and 3D visuals.
5. Add a fruit, a 500 ml juice and a 250 g dry fruit to the cart.
6. Check out; the backend checks phone, address, radius and stock; pay by UPI reference.
7. Owner verifies payment; order moves through PACKING, READY, OUT FOR DELIVERY, DELIVERED.
8. Customer leaves a review.
9. Owner adds a product with sizes and a photo; the 3D visual is created; the product appears publicly.
10. Owner creates an offer, it appears; an expired offer does not.
11. Unverified order expires after 24 hours and its stock is restored.
12. Admin creates a second owner and store, approves it (FSSAI required), sees analytics.
13. Owner A cannot read or change Owner B's products, stock, offers or orders.


KNOWN ISSUES

- Database migration not applied on the development database: the expiry job fails with "column orders.seller_delivery_available does not exist". Fix: back up, then alembic upgrade head.
- No products visible to customers until seed data is loaded and the store is approved by the admin.
- No owner dashboard in the browser yet (planned).
- OTP uses test mode; no real SMS provider is connected. The sms_service prints codes to the console.
- Owner UPI ID must be saved before customers can pay; otherwise checkout shows an error.


ROADMAP

- Verify and fix the migration and expiry job.
- Review direct UPI lifecycle end to end.
- Real SMS provider (DLT registration in India).
- Juice and dry-fruit frontend (type switch, variant picker, food info).
- Customer flow: map picker, cart, checkout, payment page, order tracking.
- Owner dashboard and admin dashboard.
- Polish: loading and error states, accessibility, mobile layout.
- Launch: real store location, new SECRET_KEY, OTP_DEV_MODE=false, real SMS and payment provider, HTTPS, backups, cloud uploads, legal pages, Android app.


SECURITY AND LAUNCH NOTES

- Never commit .env or credentials.
- Replace the development seed logins and passwords before launch; never seed a live database.
- Owners see only their own products, stock, offers and orders.
