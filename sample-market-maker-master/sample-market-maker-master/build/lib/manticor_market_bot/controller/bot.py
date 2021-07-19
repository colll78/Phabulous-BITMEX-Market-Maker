import time, pandas
from manticor_market_bot.model.data import Data
from manticor_market_bot.controller.static_instances import manticoreLog #orderManager
from market_maker.custom_strategy import CustomOrderManager
from decimal import Decimal
from manticor_market_bot.controller.coinmarketcap import getCoin, getPrice

#WAIT_TIME = 10

def toNearest(num, round_interval):
    numDec = Decimal(str(round_interval))
    return float((Decimal(round(num / round_interval, 0)) * numDec))

class Bot:
    def __init__(self):
        self.didTerminate = False
        self.orderManager = None
        self.data = Data()
        self.currTime = time.time()
        self.startFunds = 0
        self.lastUpdated = {"bestAsk": self.currTime, "bestBid": self.currTime, "createBulkOrders": self.currTime, "amendBulkOrders": self.currTime, "openOrders": self.currTime, "funds": self.currTime}
        self.bestAsk = 0
        self.sellPos = 0
        self.bestBid = 0
        self.buyPos = 0
        self.waitTime = 0
        self.orderPairs = 6
        self.orderStartQty = 100
        self.orderStepQty = 100
        self.position = 0
        self.localAllOrders = {}
        self.localCurrentOrders = {}
        self.localFilledOrders = {}
        self.marketAllOrders = {}
        self.marketCurrentOrders = {}
        self.marketFilledOrders = {}
        self.qntFilled = {}
        self.recentAsks = []
        self.toCreate = []
        self.toAmend = []
        self.maxPosition = 1000
        self.minPosition = -1000
        self.coinName = False

    def initOrderManager(self):
        self.orderManager = CustomOrderManager(self.data.config['symbol'], self.data.config['apiKey'], self.data.config['apiSecret'])

    def sanityCheck(self):
        return True

    def updateAsk(self):
        if time.time() - self.lastUpdated["bestAsk"] > -1:
            ticker = self.orderManager.exchange.get_ticker()
            self.bestAsk = getPrice(self.coinName) if self.data.config['dataSource'] == 'CoinMarketCap' else ticker['sell']
            self.recentAsks.append(self.bestAsk)
            if len(self.recentAsks) >= 200:
                del self.recentAsks[100:]
            self.lastUpdated["bestAsk"] = time.time()
            #manticoreLog.info("Best Ask: %s" % self.bestAsk)

    def updateBid(self):
        if time.time() - self.lastUpdated["bestBid"] > -1:
            ticker = self.orderManager.exchange.get_ticker()
            if self.data.config['dataSource'] == "CoinMarketCap":
                self.bestBid = getPrice(self.coinName)
            else:
                self.bestBid = ticker["buy"]
            self.lastUpdated["bestBid"] = time.time()
            #manticoreLog.info("Best Bid: %s" % self.bestBid)

    def updateOrderValues(self):
        self.updateAsk()
        self.updateBid()
        if self.data.config['dataSource'] == "CoinMarketCap":
            self.buyPos = self.bestBid - self.orderManager.instrument['tickSize']
            self.sellPos = self.bestAsk + self.orderManager.instrument['tickSize']
        else:
            self.buyPos = self.bestBid + self.orderManager.instrument['tickSize']
            self.sellPos = self.bestAsk - self.orderManager.instrument['tickSize']

        if self.buyPos == self.orderManager.exchange.get_highest_buy()['price']:
            self.buyPos = self.bestBid
        if self.sellPos == self.orderManager.exchange.get_lowest_sell()['price']:
            self.sellPos = self.bestAsk

        if self.buyPos * (1 + self.data.config['minSpread']) > self.sellPos:
            self.buyPos = (1 - (self.data.config['minSpread'] / 2)) * self.buyPos
            self.sellPos = (1 + (self.data.config['minSpread'] / 2)) * self.sellPos

    def createOrder(self, pos):
        price = self.getOrderPrice(pos)
        newOrder = {}
        quantity = self.orderStartQty + (abs(pos) - 1) * self.orderStepQty
        if pos < 0:
            newOrder = {'orderQty': quantity, 'price': price, 'side': "Buy"}
            #manticoreLog.info("Buy Position: %s" % price)
        else:
            newOrder = {'orderQty': quantity, 'price': price, 'side': "Sell"}
            #manticoreLog.info("Sell Position: %s" % price)
        self.toCreate.append(newOrder)

    def getOrderPrice(self, pos):
        price = self.buyPos if pos < 0 else self.sellPos
        if pos < 0:
            pos += 1
        else:
            pos -= 1

        adjPrice = toNearest(price * (1 + self.data.config["aggressiveness"]) ** pos, self.orderManager.instrument['tickSize'])
        # manticoreLog.info("tick size: %s" % orderManager.instrument['tickSize'])
        # manticoreLog.info("Preadjusted: %s" % price)
        # manticoreLog.info("Order Price: %s" % (price * (1 + self.data.config["aggressiveness"]) ** pos))
        lowSell = self.lowestSellOrder()
        if pos < 0 and adjPrice > lowSell:
            adjPrice = lowSell - self.orderManager.instrument['tickSize']
        highBuy = self.highestBuyOrder()
        if pos >= 0 and adjPrice < highBuy:
            adjPrice = highBuy + self.orderManager.instrument['tickSize']
        return adjPrice

    def submitOrders(self):
        if time.time() - self.lastUpdated["createBulkOrders"] > self.waitTime:
            self.updateOrderValues()
            #manticoreLog.info("Placing Orders:")
            orderPos = reversed([i for i in range(1, self.orderPairs)])
            for i in orderPos:
                self.createOrder(-i)
                self.createOrder(i)
            buyOrders = [o for o in self.toCreate if o['side'] == "Buy"]
            sellOrders = [o for o in self.toCreate if o['side'] == "Sell"]
            self.toCreate.clear()
            self.lastUpdated["createBulkOrders"] = time.time()
            self.mergeOrders(buyOrders, sellOrders)

    def mergeOrders(self, buyOrders, sellOrders):
        buy_to_merge = 0
        sell_to_merge = 0
        to_change = []
        to_add = []
        to_remove = []

        self.localUpdate()

        for o in self.marketCurrentOrders:
            if o['side'] == "Buy":
                if buy_to_merge < len(buyOrders):
                    newOrd = buyOrders[buy_to_merge]
                    buy_to_merge += 1
                else:
                    to_remove.append(o)
                    continue
            else:
                if sell_to_merge < len(sellOrders):
                    newOrd = sellOrders[sell_to_merge]
                    sell_to_merge += 1
                else:
                    to_remove.append(o)
                    continue

            if newOrd['orderQty'] != o['leavesQty']:
                self.qntFilled[o['clOrdID']] = self.qntFilled.get(o['clOrdID'], o['orderQty'])
                num_filled = self.qntFilled[o['clOrdID']] - o['leavesQty']
                manticoreLog.info("num_filled: %s" % num_filled)
                manticoreLog.info("price: %s" % o["price"])
                self.qntFilled[o['clOrdID']] = self.qntFilled[o['clOrdID']] - num_filled
                self.data.feeProfit += Decimal(str(o["price"])) * Decimal(str(num_filled)) * Decimal(str(0.000250))
                manticoreLog.info("Fee Profit: %s" % self.data.feeProfit)

            if newOrd['orderQty'] != o['leavesQty'] or abs((newOrd['price'] / o['price']) - 1) > self.data.config[
                "relistThreshold"]:
                to_change.append(
                    {'orderID': o['orderID'], 'orderQty': o['cumQty'] + newOrd['orderQty'], 'price': newOrd['price'],
                     'side': o['side']})

        while buy_to_merge < len(buyOrders):
            to_add.append(buyOrders[buy_to_merge])
            buy_to_merge += 1

        while sell_to_merge < len(sellOrders):
            to_add.append(sellOrders[sell_to_merge])
            sell_to_merge += 1

        if to_change:
            try:
                self.orderManager.exchange.amend_bulk_orders(to_change)
            except:
                return self.submitOrders()

        if to_add:
            buyOrders = [o for o in to_add if o['side'] == "Buy"]
            sellOrders = [o for o in to_add if o['side'] == "Sell"]
            self.data.numBuy += len(buyOrders)
            self.data.numSell += len(sellOrders)
            self.orderManager.exchange.create_bulk_orders(to_add)

        if to_remove:
            self.orderManager.exchange.cancel_bulk_orders(to_remove)


    def highestBuyOrder(self):
        max = {"price": 0}
        for order in self.toCreate:
            if (order["side"] == "Buy") & (order["price"] > max["price"]):
                max = order
        return max['price']

    def lowestSellOrder(self):
        min = {"price": float("inf")}
        for order in self.toCreate:
            if (order["side"] == "Sell") & (order["price"] < min["price"]):
                min = order
        return min['price']

    def localUpdate(self):
        if time.time() - self.lastUpdated["openOrders"] > -1:
            self.marketAllOrders = self.orderManager.exchange.bitmex.all_orders()
            self.marketCurrentOrders = self.orderManager.exchange.bitmex.open_orders()
            manticoreLog.info(self.marketCurrentOrders)
            self.marketFilledOrders = self.orderManager.exchange.bitmex.filled_orders()
            self.data.orderbook = self.marketCurrentOrders
            manticoreLog.info(self.marketFilledOrders)
            self.lastUpdated["openOrders"] = time.time()
            #manticoreLog.info("Filled Orders: %s" % self.marketFilledOrders)

    def updateProfit(self):
        if time.time() - self.lastUpdated["funds"] > 10:
            balance = self.orderManager.exchange.bitmex.funds()["walletBalance"]
            self.data.updateProfit(self.startFunds, balance)
            self.data.walletBalance = balance
            #manticoreLog.info("Available funds: %s" % orderManager.exchange.bitmex.funds()['availableMargin'])
            #manticoreLog.info("Total equity value: %s" % orderManager.exchange.bitmex.funds()['amount'])
            #manticoreLog.info("Available funds: %s" % self.orderManager.exchange.bitmex.funds())
            manticoreLog.info("Total Profit: %s" % self.data.marketProfitTotal)

            self.lastUpdated["funds"] = time.time()

    def minPositionCheck(self):
        if self.orderManager.exchange.get_delta() <= self.minPosition:
            return True
        return False

    def maxPositionCheck(self):
        if self.orderManager.exchange.get_delta() >= self.maxPosition:
            return True
        return False

    def start(self):
        self.initOrderManager()
        if self.data.config["dataSource"] == "CoinMarketCap":
            self.waitTime = 20
            self.coinName = getCoin(self.data.config["symbol"])
        else:
            self.waitTime = 10
        self.startFunds = self.orderManager.exchange.bitmex.funds()["walletBalance"]
        if self.startFunds >= self.data.cryptoAmount:
            manticoreLog.info("Funds: %s" % self.orderManager.exchange.bitmex.funds())
            self.run()

    def run(self):
        while not self.didTerminate:
            if time.time() - self.currTime > self.data.config['terminateTime']:
                self.didTerminate = True
            self.sanityCheck()
            self.updateProfit()
            self.data.rateOfChange(self.recentAsks)
            if self.data.marketTrend == "Low":
                self.position = 1
            elif self.data.marketTrend == "High":
                recentRates = pandas.Series(self.recentAsks[(len(self.recentAsks)-11):]).pct_change()
                recentRateOfChange = recentRates.sum() / recentRates.size
                if recentRateOfChange > .015:
                    self.position = -1
            else:
                self.submitOrders()
        self.orderManager.exchange.cancel_all_orders()