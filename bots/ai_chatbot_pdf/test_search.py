import asyncio
from telegram_bot.services.vector_store import similarity_search

async def test():
    docs = await similarity_search('what is VHA', user_id=6339567576)
    print(f'Found {len(docs)} documents')
    for doc in docs:
        print(doc.page_content[:100])

asyncio.run(test())
