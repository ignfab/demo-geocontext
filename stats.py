import asyncio
from db import create_database, get_thread_ids
from agent import build_graph, get_messages
import csv
import sys


async def compute_stats():
    async with create_database() as db:
        graph = await build_graph(db.checkpointer)
        thread_ids = await get_thread_ids(db.checkpointer)
        
        writer = csv.writer(sys.stdout)
        writer.writerow([
            'THREAD_ID',
            'MESSAGE_COUNT',
            'MESSAGE_DATE',
            'MESSAGE_TYPE',
            'INPUT_TOKENS',
            'OUTPUT_TOKENS',
            'TOTAL_TOKENS',
            'MESSAGE_CONTENT'
        ])
        for thread_id in thread_ids:
            message_count = 0
            async for message, message_date in get_messages(graph, thread_id):
                message_count += 1
                if hasattr(message,'usage_metadata'):
                    input_token = message.usage_metadata['input_tokens']
                    output_tokens = message.usage_metadata['output_tokens']
                    total_tokens = message.usage_metadata['total_tokens']
                else:
                    input_token = 0
                    output_tokens = 0
                    total_tokens = 0
                    
                message_content="NA"
                if message.type == "human":
                    message_content =  message.text()
                    
                writer.writerow([
                    thread_id,
                    message_count,
                    message_date,
                    message.type,
                    input_token,
                    output_tokens,
                    total_tokens,
                    message_content
                ])

if __name__ == '__main__':
    asyncio.run(compute_stats())
