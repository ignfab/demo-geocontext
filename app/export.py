import asyncio

import csv
import sys
from .services.db import get_database, get_thread_ids
from .services.agent import get_agent_no_tools, get_messages


async def export_messages():
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

    async with get_database() as db:
        thread_ids = await get_thread_ids(db)
    
        async with get_agent_no_tools() as agent:
            for thread_id in thread_ids:
                message_count = 0
                async for message, message_date in get_messages(agent, thread_id):
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
                        message_content =  message.text
                        
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
    asyncio.run(export_messages())
