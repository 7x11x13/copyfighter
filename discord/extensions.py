import os

from cloudflare import Cloudflare
from dotenv import load_dotenv

load_dotenv()

client = Cloudflare()
database = client.d1.database


def query(sql: str, params: list = None):
    return database.query(
        database_id=os.getenv("D1_DATABASE_ID"),
        account_id=os.getenv("CLOUDFLARE_ACCOUNT_ID"),
        sql=sql,
        params=params,
    )
