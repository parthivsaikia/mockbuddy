# create_tables.py

# This line is crucial to load the DATABASE_URL from your .env file
from dotenv import load_dotenv
load_dotenv()

# Import the 'Base' object and the 'engine' from your app's database setup
from app.db.database import Base, engine
# Make sure you import all your models here so Base knows about them!
from app.models import db_models  # This assumes your models are in app/db/models.py

print("Connecting to the database and creating tables...")

# This is the magic command that creates all tables
Base.metadata.create_all(bind=engine)

print("Tables created successfully!")
