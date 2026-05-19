**Some general rules we follow**

1. We use Unix Filetypes
2. Code-Style: Halte den Code lesbar. Nutze sprechende Variablen- und Funktionsnamen.
3. Python compatibility: Ideally, the code should be written so that it runs on both Python 2.7 and Python 3.x.
4. No heavy external dependencies: For HTTP requests, use the tools built into E2iPlayer (pCommon, urllib, etc.) instead of heavy external libraries that require a tedious installation process on the receivers.
5. Try to see if you can open links using one of the existing parsers before you write a new parser
6. Most websites have security measures in place to prevent links from being exported, and you shouldn't try to bypass them in a way that gets noticed; instead, you should get around them without them noticing—as if you were logging in using a browser.
7. 
