import os
from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def process_news(articles):
    if not os.getenv("GROQ_API_KEY"):
        print("GROQ API KEY NAHI MIL RAHI "
              "SAB KHATAM HO JAYEGA AB TOH")

    for index, article in enumerate(articles, start=1):

        prompt = f"""
You are a news assistant.

Read the following news article.

Your tasks are:

1. Categorize the news into ONLY ONE of these categories:
Technology,
Business,
Sports,
Politics,
Entertainment,
Health,
Science,
World,
Other

2. Write a summary in 2-3 sentences.

Return your answer EXACTLY in this format.

Category: <category>
Summary: <summary>

News Title:
{article["title"]}

News Description:
{article["description"]}
"""
        try:
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2
            )
            result = response.choices[0].message.content

        except Exception as e:
            print("KUCH TOH FAT GAYA, PATA NAHI KYA")
            continue  

        lines = result.split("\n")

        for line in lines:
            clean_line = line.strip().lstrip("*").strip()
            if clean_line.startswith("Category:"):
                article["category"] = clean_line.replace("Category:", "").strip()
            elif clean_line.startswith("Summary:"):
                article["summary"] = clean_line.replace("Summary:", "").strip()

        if article["category"] is None or article["summary"] is None:
            print("faileddd")

    return articles