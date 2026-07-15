import requests
from app import the_news

TOKEN = "8835333521:AAGLp7jrUliXLhpVqYol42cStsOwo9M-Wxc"
chat_id = "1148674997"
message = the_news()
linkkk = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={chat_id}&text={message}"
print(requests.get(linkkk).json())


# okayy so whatever change I do in here, they must not reflect back 
# in the master branch since this is a send_message branch