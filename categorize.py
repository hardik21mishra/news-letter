import os
import json
import traceback
from groq import Groq
from fetch_news import fetch_news

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("GROQ_API_KEY environment variable not found!")

client = Groq(api_key=api_key)

articles = fetch_news()

print(f"\nFetched {len(articles)} articles.\n")

def process_news(articles):

    for index, article in enumerate(articles, start=1):

        print(f"Processing article {index}/{len(articles)}")
        article["summary"] = None

        prompt = f"""
You are a news assistant.

Read the following news article.

Your task is:

1. Write a concise technical summary in 40 - 60 words strictly, the summary should not contain any unnatural characters but only text.

Return your answer EXACTLY in this format.

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

            # print(result)

            lines = result.split("\n")

            for line in lines:
                clean_line = line.strip().lstrip("*").strip()

                if clean_line.startswith("Summary:"):
                    article["summary"] = clean_line.replace("Summary:", "").strip()
                    break

            if article["summary"] is None:
                print(f"Couldn't parse summary for article {index}")
                print("Model Output:")
                print(result)
                print("-" * 60)

        except Exception as e:
            print(f"\nError while processing article {index}")
            print(f"Title: {article['title']}")
            print(f"Reason: {e}")
            traceback.print_exc()
            print("-" * 80)
            continue

    return articles


# from to_excel import export_to_excel

# file_name = export_to_excel(summarized_articles)

# print("\nNews saved successfully to", file_name)