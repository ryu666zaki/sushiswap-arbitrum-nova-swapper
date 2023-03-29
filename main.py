import random
from web3 import Web3
import json
from termcolor import cprint
import time
from tqdm import tqdm

# Устанавливаем кол-во кругов транзакий. 1 круг - 2 транзакции. (ETH -> USDC | USDC -> ETH)

# Введите список приватных ключей
private_keys = [
    'приватник1',
    'приватник2',
    # и тд.
]

# Инициализация провайдера и контрактов
nova_rpc = 'https://nova.arbitrum.io/rpc'  # Введите URL вашего провайдера
w3 = Web3(Web3.HTTPProvider(nova_rpc))
nova_scan = 'https://nova.arbiscan.io/tx'
chain_id = 42170

sushi_router_address = Web3.to_checksum_address('0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506')
router_abi = json.load(open('abi.json', 'r'))
sushi_router = w3.eth.contract(address=sushi_router_address, abi=router_abi)

# Константы
WETH = Web3.to_checksum_address('0x722e8bdd2ce80a4422e880164f2079488e115365')
USDC = Web3.to_checksum_address('0x750ba8b76187092B0D1E87E28daaf484d1b5273b')

# Словарь для хранения первоначальных балансов
initial_eth_balance = {}

# Время ожидания между транзакциями
sleep_time_min = 2
sleep_time_max = 3


def sleeping(from_sleep, to_sleep):
    x = random.randint(from_sleep, to_sleep)
    for _ in tqdm(range(x), desc='sleep ', bar_format='{desc}: {n_fmt}/{total_fmt}'):
        time.sleep(1)


def main():
    count = 0
    while count < 10:
        for key in private_keys:
            account = w3.eth.account.from_key(key)
            address = account.address

            # Получение балансов
            eth_balance = w3.eth.get_balance(address)
            usdc_balance = w3.eth.call({"to": USDC, "data": f"0x70a08231{address[2:].zfill(64)}"}, 'latest')
            usdc_balance = int(usdc_balance.hex(), 16)

            # Запомнить начальный баланс, если его нет в словаре
            if address not in initial_eth_balance:
                initial_eth_balance[address] = eth_balance

            # Выбор направления свапа и суммы
            if eth_balance > initial_eth_balance[address] * 0.9:
                swap_direction = WETH
                swap_amount = int(eth_balance - (eth_balance / 5))
            elif usdc_balance > 0:
                swap_direction = USDC
                swap_amount = usdc_balance
            else:
                continue

            # Подготовка и отправка транзакции
            if swap_direction == WETH:
                deadline = w3.eth.get_block("latest")["timestamp"] + 300
                path = [WETH, USDC]
                amount_out_min = 0

                txn = sushi_router.functions.swapExactETHForTokens(
                    amount_out_min, path, address, deadline
                ).build_transaction({
                    "from": address,
                    "value": swap_amount,
                    "gasPrice": w3.eth.gas_price,
                    "nonce": w3.eth.get_transaction_count(address),
                })
            else:  # swap_direction == USDC
                deadline = w3.eth.get_block("latest")["timestamp"] + 300
                path = [USDC, WETH]
                amount_out_min = 0
                max_amount = w3.to_wei(2 ** 64 - 1, 'ether')
                max_amount_hex = w3.to_hex(max_amount)[2:].zfill(64)

                # Разрешение на списание USDC
                transaction = {
                    "from": address,
                    "to": USDC,
                    "data": f"0x095ea7b3{sushi_router_address[2:].zfill(64)}{max_amount_hex}",
                    "gasPrice": w3.eth.gas_price,
                    "nonce": w3.eth.get_transaction_count(address),
                }
                gas_estimate = w3.eth.estimate_gas(transaction)
                transaction["gas"] = gas_estimate
                approve_txn = w3.eth.account.sign_transaction(transaction, key)
                tx_hash = w3.eth.send_raw_transaction(approve_txn.rawTransaction)
                cprint(f'\n>>> USDC Approved | {nova_scan}/{w3.to_hex(tx_hash)}', 'green')

                txn = sushi_router.functions.swapExactTokensForETH(
                    swap_amount, amount_out_min, path, address, deadline
                ).build_transaction({
                    "from": address,
                    "gasPrice": w3.eth.gas_price,
                    "nonce": w3.eth.get_transaction_count(address)+1,
                })
            try:
                signed_txn = w3.eth.account.sign_transaction(txn, key)
                tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)

                cprint(f'\n>>> {nova_scan}/{w3.to_hex(tx_hash)}', 'green')
            except Exception as error:
                cprint(f'\n>>> {error}', 'red')

            sleeping(sleep_time_min, sleep_time_max)
        count += 1


if __name__ == "__main__":
    main()
