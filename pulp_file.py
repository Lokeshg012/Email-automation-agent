import os
import time
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# The API key is loaded from your .env file
client = OpenAI()

# Upload your strategy file with the correct purpose
print("Uploading file...")
file = client.files.create(
  file=open("pulp_strategy.docx", "rb"),
  purpose="assistants" # The fix is here
)
print(f"File uploaded with ID: {file.id}")

# Create an Assistant with File Search enabled
print("Creating Assistant...")
assistant = client.beta.assistants.create(
  name="Strategy Analyst",
  instructions="You are an expert business analyst. Use the provided strategy documents to answer questions accurately.",
  model="gpt-4o-mini",
  tools=[{"type": "file_search"}]
)
print(f"Assistant created with ID: {assistant.id}")

# Create a Thread (a conversation session)
print("Creating a new thread...")
thread = client.beta.threads.create()
print(f"Thread created with ID: {thread.id}")

# Add your prompt (message) to the Thread and attach the file
print("Adding message to the thread...")
message = client.beta.threads.messages.create(
    thread_id=thread.id,
    role="user",
    content="According to the strategy document, who is the target audience for our marketing efforts?",
    attachments=[
        {"file_id": file.id, "tools": [{"type": "file_search"}]}
    ]
)

# Run the Assistant to process the message
print("Running the assistant...")
run = client.beta.threads.runs.create(
  thread_id=thread.id,
  assistant_id=assistant.id,
)

# Wait for the Run to complete
print("Waiting for the run to complete...")
while run.status not in ["completed", "failed"]:
    time.sleep(1)
    run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
    print(f"Current run status: {run.status}")

if run.status == "completed":
    # Retrieve and display the messages
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    response = messages.data[0].content[0].text.value
    print("\n✅ Assistant's Response:")
    print(response)
else:
    print(f"\n❌ Run failed with status: {run.status}")