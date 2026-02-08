import requests

TOKEN = "8561942994:AAE9L5BnSpyo5H5FVYQJQZpIP4Bt_K-YFO4"

try:
    url = f"https://api.telegram.org/bot{TOKEN}/getMe"
    response = requests.get(url)
    data = response.json()
    
    if data.get("ok"):
        bot_info = data["result"]
        print("Token to'g'ri!")
        print(f"Bot nomi: {bot_info['first_name']}")
        print(f"Bot username: @{bot_info['username']}")
    else:
        print(f"Token xato: {data.get('description')}")
        
except Exception as e:
    print(f"Xatolik: {e}")
