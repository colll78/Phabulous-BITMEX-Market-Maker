import requests
r = requests.post("http://localhost:5000", data={
  "dataSource": "BitMEX",
  "apiKey": "exNVCVPa_hDetpwHDR4paEE9",
  "apiSecret": "BqUPgajs4RMRNUyjlkMfDKu38ckK0LRPrbwp1Clb70Ong9Q9",
  "symbol": "XBTUSD",
  "walletAmountCrypto": 500,
  "minSpread": 0.0002,
  "marketLowThreshold": -0.5,
  "marketHighThreshold": 0.5,
  "relistThreshold": 0.01,
  "aggressiveness": 0.0005,
  "terminateTime": 1800,
})
# And done.
print(r.text) # displays the result body.