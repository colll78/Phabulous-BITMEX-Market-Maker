import requests
from bs4 import BeautifulSoup
from decimal import Decimal

def crawl_coin_data():
    uml = 'https://coinmarketcap.com/all/views/all'
    page = requests.get(uml)
    soup = BeautifulSoup(page.text, 'html.parser')
    coins = []
    table = soup.find('tbody')
    rows = table.findChildren(['th', 'tr'])

    coins = []
    for row in rows:
        cells = row.findChildren('td')
        coin = []
        for cell in cells:
            value = cell.string
            coin.append(value)
        coins.append(coin)
    return coins

def getPrice(coinName):
    page = requests.get('https://coinmarketcap.com/all/views/all/')
    soup = BeautifulSoup(page.content, 'lxml')
    coins = []
    table = soup.find('tbody')

    for tr in table.find_all('tr'):
        coin = {}
        name_tag = tr.find('a')
        coin['name'] = name_tag.next_element
        price_tag = name_tag.find_next('a')
        coin['price'] = price_tag.next_element
        coins.append(coin)
    for coin in coins:
        if coin["name"] == coinName:
            cleanedCoin = cleanCoin(coin["price"])
            return float(cleanedCoin)
    return None

def cleanCoin(dirtyCoin):
    temp = dirtyCoin[1:].split(",")
    clean = ""
    for piece in temp:
        clean += piece
    return clean

def getCoin(symbol):
    if symbol == "XBTUSD" or "XBTJPY":
        return "Bitcoin"
    elif symbol == "ADAM20":
        return "Cardano"
    elif symbol == "BCHM20":
        return "Bitcoin Cash"
    elif symbol == "EOSM20":
        return "EOS"
    elif symbol == "ETHXBT":
        return "Ethereum"
    elif symbol == "LTCM20":
        return "Litecoin"
    elif symbol == "TRXM20":
        return "Tron"
    elif symbol == "XRPUSD":
        return "XRP"
    else:
        return None