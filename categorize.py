import os
import traceback
from groq import Groq
# from fetch_news import fetch_news

from dotenv import load_dotenv
load_dotenv()


def get_groq_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY environment variable not found. Add it to your environment or GitHub Actions secrets.")
    return Groq(api_key=api_key)

# articles = fetch_news()

# print(f"\nFetched {len(articles)} articles.\n")

LOW_VALUE_CATEGORIES = { "news", "technology", "tech", "engineering", "software", "development", "programming", "computing", "computer science", "it", "general", "general news", "top stories", "latest", "updates", "announcement", "announcements", "blog", "blogs", "articles", "featured", "editorial", "opinion", "research", "innovation", "industry", "business", "products", "release", "releases", "events", "community", "open source",}

def process_news(articles):
    client = get_groq_client()

    for index, article in enumerate(articles, start=1):
        print(f"Processing article {index}/{len(articles)}")
        article["summary"] = None

        # to avoid cases like "category": ""
        category = article.get("category")

        if isinstance(category, str):
            category = category.strip().lower()
        else:
            category = None
        if not category or category in LOW_VALUE_CATEGORIES:
            article["category"] = None
        else:
            article["category"] = category
        # --------

        if article["category"]:
            prompt = f"""
    You are a news assistant.
    Read the following news article.
    Your task is:
    1. Write a concise technical summary in 50 - 60 words, the summary should not contain any unnatural characters but only text.
    Return your answer EXACTLY in this format. 
    Summary: <summary>

    News Title:
    {article["title"]}

    News Description:
    {article["description"]}
"""   
        else:

            prompt = f"""
        You are a news assistant.

        Read the following article.

        1. Write a concise technical summary in 50-60 words.

        2. Classify it into EXACTLY ONE category from:

        AI
        Programming
        Backend
        Frontend
        Cloud
        DevOps
        Cybersecurity
        Data Science
        Database
        Networking
        Mobile
        Hardware
        Open Source
        Research
        Other(mention it according to you)

        Return EXACTLY:

        Summary: <summary>
        Category: <category>
        Also make sure to strip all the leading and trailing "*" from your category amswer
        News Title:
        {article["title"]}

        News Description:
        {article["description"]}
"""
        try:
            response = client.chat.completions.create(
                model="openai/gpt-oss-120b",
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
                elif clean_line.startswith("Category:"):
                    article["category"] = clean_line.replace("Category", "").strip()

            if article["summary"] is None:
                print(f"Couldn't generate summary for article {index}")
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