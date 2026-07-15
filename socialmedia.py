# import requests
# from app import the_news

# TOKEN = "8835333521:AAGLp7jrUliXLhpVqYol42cStsOwo9M-Wxc"
# chat_id = "1148674997"
# message = the_news()

# # print(message)

# for dic in message:    
#     for key, value in dic.items():
#         link = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={chat_id}&text={key, value}"
#         print(requests.get(link).json())


import requests
from app import the_news

TOKEN = "8835333521:AAGLp7jrUliXLhpVqYol42cStsOwo9M-Wxc"
chat_id = "1148674997"
message = the_news()

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

for article in message:
    text = (
        article["title"] + "\n"
        + "Category: " + article["category"] + "\n"
        + article["summary"] + "\n"
        + "Published: " + article["published_date"]
    )
    print(requests.post(url, data={"chat_id": chat_id, "text": text}).json())