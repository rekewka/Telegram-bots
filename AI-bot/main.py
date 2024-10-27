import config
import asyncio
from typing_extensions import override
from openai import AssistantEventHandler, OpenAI

from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command


client = OpenAI(api_key=config.ai)

bot_token = config.bot

ai_token = config.ai

bot = Bot(bot_token)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_bot(msg : types.Message):
    if msg.chat.type == 'supergroup' or msg.chat.type == 'group':
        await msg.answer(config.start_msg)
    else:
        await msg.reply(config.start_msg)

@dp.message()
async def text_bot(msg : types.Message):
    assistant = client.beta.assistants.create(
        name="Оператор",
        instructions="Используй ответы с test.txt",
        model="gpt-4o",
        tools=[{"type": "file_search"}],
    )

    vector_store = client.beta.vector_stores.create(name="Оператор")

    file_paths = ["test.txt"]
    file_streams = [open(path, "rb") for path in file_paths]
    file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
        vector_store_id=vector_store.id, files=file_streams
    )

    assistant = client.beta.assistants.update(
        assistant_id=assistant.id,
        tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
    )

    message_file = client.files.create(
        file=open("test.txt", "rb"), purpose="assistants"
    )

    thread = client.beta.threads.create(
        messages=[
            {
                "role": "user",
                "content": msg.text,
                "attachments": [
                    {"file_id": message_file.id, "tools": [{"type": "file_search"}]}
                ],
            }
        ]
    )

    class EventHandler(AssistantEventHandler):
        def __init__(self):
            super().__init__()
            self.ans = ""

        @override
        def on_message_done(self, message) -> None:
            message_content = message.content[0].text
            annotations = message_content.annotations
            citations = []
            for index, annotation in enumerate(annotations):
                message_content.value = message_content.value.replace(
                    annotation.text, f"[{index}]"
                )
                if file_citation := getattr(annotation, "file_citation", None):
                    cited_file = client.files.retrieve(file_citation.file_id)
                    citations.append(f"[{index}] {cited_file.filename}")

            for i in range(len(message_content.value)):
                if message_content.value[i] == '[' and message_content.value[i + 1] >= '0' and message_content.value[ i + 1] <= '9':
                    break
                self.ans += message_content.value[i]

    event_handler = EventHandler()

    with client.beta.threads.runs.stream(
            thread_id=thread.id,
            assistant_id=assistant.id,
            instructions="",
            event_handler=event_handler,
    ) as stream:
        stream.until_done()

    if msg.chat.type == 'supergroup' or msg.chat.type == 'group':
        await msg.answer(event_handler.ans)
    else:
        await msg.answer(event_handler.ans)


async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())



