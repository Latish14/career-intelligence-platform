import os
from dotenv import load_dotenv

load_dotenv()

print("APP_ID =", os.getenv("ADZUNA_APP_ID"))
print("APP_KEY =", os.getenv("ADZUNA_APP_KEY"))