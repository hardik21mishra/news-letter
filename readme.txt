project ---> NewsLetter ---> sends the summaries of top news to different users 

step 1. fetch news from the web in fetch_news.py file
        -- use rss feed 
        -- print some news to check

step 2. we have the different news articles from different sources ---> categorise + summarise
        -- classify the news in different categories now like:
            - sports
            - general
            - latest
            - etc.
        -- summarise the news using the groq free api
        -- end result: will have the unfilled column of categories and summaries filled

step 3. combine both the functions of step 1 and step 2 in single file ---> app.py
            - get the category and summary field filled 

step 4. (figure out - how to send newsletter via telegram using py script)
        send the news updates to users on social media personally 
            - telegram
