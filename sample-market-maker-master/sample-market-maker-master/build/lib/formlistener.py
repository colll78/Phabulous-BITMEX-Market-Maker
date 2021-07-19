import requests
from manticor_market_bot.controller.bot import Bot
from bs4 import BeautifulSoup
from flask import Flask, request, make_response, jsonify

app = Flask(__name__)

def _build_cors_prelight_response():
    response = make_response()
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "*")
    response.headers.add("Access-Control-Allow-Methods", "*")
    return response

def _corsify_actual_response(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response

mantibot = Bot()

@app.route('/', methods=['POST','OPTIONS'])
def result():
    if request.method == "OPTIONS":  # CORS preflight
        return _build_cors_prelight_response()
    elif request.method == "POST":  # The actual request following the preflight
        mantibot.data.updateConfigs(request.form.to_dict())
        print(mantibot.data.config)
        mantibot.start()
        return _corsify_actual_response(jsonify("RECEIVED!"))

@app.route('/exchanges', methods=['GET', 'OPTIONS'])
def give_exchange_data():
    print(request.method)
    if request.method == "OPTIONS":
        return _build_cors_prelight_response()
    elif request.method == "GET":
        return _corsify_actual_response(jsonify(crawl_coin_data()))

@app.route('/botdata', methods=['GET', 'OPTIONS'])
def give_bot_data():
    if request.method == "OPTIONS":
        return _build_cors_prelight_response()
    elif request.method == "GET":
        return _corsify_actual_response(jsonify(get_bot_data()))

def get_bot_data():
    bot_data = {}
    bot_data['feeProfit'] = float(mantibot.data.feeProfit)
    bot_data['numBuy'] = mantibot.data.numBuy
    bot_data['numSell'] = mantibot.data.numSell
    bot_data['marketTrend'] = mantibot.data.marketTrend
    bot_data['marketProfitTotal'] = float(mantibot.data.marketProfitTotal)
    bot_data['orderbook'] = []
    for order in mantibot.data.orderbook:
        bot_data['orderbook'].append({'price': order['price'], 'size': order['orderQty'], 'total': (order['price'] * order['orderQty']), 'side': order['side']})
    return bot_data

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

if __name__ == "__main__":
    app.run(host="0.0.0.0")
