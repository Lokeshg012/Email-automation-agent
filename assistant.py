import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI()

file = client.files.create(
  file=open("pulp_strategy.docx", "rb"),
  purpose="assistants"
)
print(f"File uploaded with ID: {file.id}")

assistant = client.beta.assistants.create(
  name="Pulp Strategy Email Specialist",
  instructions="You are a business development expert for Pulp Strategy...",
  model="gpt-4o-mini",
  tools=[{"type": "file_search"}]
)
print(f"Assistant created with ID: {assistant.id}")

thread = client.beta.threads.create()
print(f"Permanent Thread created with ID: {thread.id}")

# 4. Save the IDs to your .env file
with open(".env", "a") as env_file:
    env_file.write("\n")
    env_file.write(f"ASSISTANT_ID={assistant.id}\n")
    env_file.write(f"FILE_ID={file.id}\n")
    env_file.write(f"THREAD_ID={thread.id}\n")

print("\n✅ Setup complete! Your .env file has been updated with the new IDs.")