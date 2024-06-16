import json
import requests
from web3 import Web3, HTTPProvider
from web3.middleware import geth_poa_middleware
from eth_account import Account
from eth_account.messages import encode_defunct
import time
from random import choice
from anticaptchaofficial.recaptchav2proxyon import recaptchaV2Proxyon
from itertools import cycle
from datetime import datetime
from settings import ANTI_CAPTCHA_KEY, CAPTCHASUKA, RPC_URL, SITE_KEY, claim_abi, SEND_EXCHANGE, POTOK
from concurrent.futures import ThreadPoolExecutor

# Константы
API_KEY = '46001d8f026d4a5bb85b33530120cd38'
ELIGIBILITY_API_URL = 'https://api.zknation.io/eligibility'
CLAIM_CONTRACT_ADDRESS = '0x903fA9b6339B52FB351b1319c8C0411C044422dF'
TOKEN_CONTRACT_ADDRESS = '0x5A7d6b2F92C77FAD6CCaBd7EE0624E64907Eaf3E'
PROXY_FILE_PATH = 'proxies.txt'  # Путь к файлу с прокси
KEYS_FILE_PATH = 'keys.txt'  # Путь к файлу с приватными ключами
SUB_ACCS_FILE_PATH = 'sub_accs.txt'  # Путь к файлу с адресами для отправки токенов

# Инициализация веб3
web3 = Web3(HTTPProvider(RPC_URL))
web3.middleware_onion.inject(geth_poa_middleware, layer=0)

# Чтение ABI функции claimOnBehalf
"""
claim_abi = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "_index", "type": "uint256"},
            {"internalType": "uint256", "name": "_amount", "type": "uint256"},
            {"internalType": "bytes32[]", "name": "_merkleProof", "type": "bytes32[]"},
            {
                "components": [
                    {"internalType": "address", "name": "claimant", "type": "address"},
                    {"internalType": "uint256", "name": "expiry", "type": "uint256"},
                    {"internalType": "bytes", "name": "signature", "type": "bytes"}
                ],
                "internalType": "struct ZkMerkleDistributor.ClaimSignatureInfo",
                "name": "_claimSignatureInfo",
                "type": "tuple"
            }
        ],
        "name": "claimOnBehalf",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]
"""
# Чтение ABI стандарта ERC-20 для проверки баланса
erc20_abi = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"name": "success", "type": "bool"}],
        "type": "function"
    }
]

# Функция для загрузки прокси из файла
def load_proxies(file_path):
    with open(file_path, 'r') as file:
        proxies = [line.strip() for line in file]
    return proxies

# Функция для загрузки приватных ключей из файла
def load_private_keys(file_path):
    with open(file_path, 'r') as file:
        keys = [line.strip() for line in file]
    return keys

# Функция для загрузки адресов для отправки токенов из файла
def load_sub_accounts(file_path):
    with open(file_path, 'r') as file:
        addresses = [Web3.to_checksum_address(line.strip()) for line in file]
    return addresses

# Функция для получения случайного прокси
def get_random_proxy(proxies):
    proxy = choice(proxies)
    ip, port, user, password = proxy.split(':')
    return {
        'http': f'socks5://{user}:{password}@{ip}:{port}',
        'https': f'socks5://{user}:{password}@{ip}:{port}'
    }, proxy

# Функция для обработки капчи
def solve_captcha(proxy):
    solver = recaptchaV2Proxyon()
    solver.set_verbose(1)
    solver.set_key(ANTI_CAPTCHA_KEY)
    solver.set_website_url(ELIGIBILITY_API_URL)
    solver.set_website_key(SITE_KEY)  # Замените на реальный ключ сайта (site key)
    ip, port, user, password = proxy.split(':')
    solver.set_proxy_address(ip)
    solver.set_proxy_port(port)
    solver.set_proxy_login(user)
    solver.set_proxy_password(password)

    captcha_solution = solver.solve_and_return_solution()
    if captcha_solution != 0:
        print("Captcha solved: " + captcha_solution)
        return captcha_solution
    else:
        print("Error solving captcha: " + solver.error_code)
        return None

# Функция для получения данных о пользователе
def get_user_data(wallet_address, proxies):
    headers = {
        'X-Api-Key': API_KEY,
        'Content-Type': 'application/json'
    }
    params = {'id': wallet_address}
    proxy_dict, proxy = get_random_proxy(proxies)

    if CAPTCHASUKA:
        captcha_solution = solve_captcha(proxy)
        if captcha_solution:
            params['g-recaptcha-response'] = captcha_solution
        else:
            raise Exception("Captcha solving failed")

    response = requests.get(ELIGIBILITY_API_URL, headers=headers, params=params, proxies=proxy_dict)
    response.raise_for_status()
    return response.json()

# Функция для отправки транзакции
def send_claim_transaction(web3, index, amount, merkle_proof, wallet_address, expiry, signature, private_key):
    contract = web3.eth.contract(address=CLAIM_CONTRACT_ADDRESS, abi=claim_abi)
    account = Account.from_key(private_key)
    nonce = web3.eth.get_transaction_count(account.address)
    #gas_price = web3.eth.gas_price
    gas_price = int(web3.eth.gas_price * 1.5)  # Увеличиваем цену газа на 50%




    transaction = contract.functions.claim(
        index,
        amount,
        merkle_proof,
        #{
            #'claimant': wallet_address,
            # 'expiry': expiry,
            #'signature': signature
        #}
    ).build_transaction({
        'chainId': web3.eth.chain_id,
        'gas': 400000,  # Увеличиваем лимит газа на 50% заменить на gaslimit когда включат контракт
        'gasPrice': gas_price,
        'nonce': nonce
    })

    signed_txn = web3.eth.account.sign_transaction(transaction, private_key=private_key)
    txn_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)
    return txn_hash.hex()

# Функция для проверки баланса токенов
def check_token_balance(web3, wallet_address):
    token_contract = web3.eth.contract(address=TOKEN_CONTRACT_ADDRESS, abi=erc20_abi)
    balance = token_contract.functions.balanceOf(wallet_address).call()
    return balance

# Функция для отправки токенов
def send_tokens(web3, private_key, to_address, balance):
    token_contract = web3.eth.contract(address=TOKEN_CONTRACT_ADDRESS, abi=erc20_abi)
    account = Account.from_key(private_key)
    nonce = web3.eth.get_transaction_count(account.address)
    gas_price = int(web3.eth.gas_price * 1.5)  # Увеличиваем цену газа на 50%
    gas_limit = int(token_contract.functions.transfer(
        to_address,
        balance
    ).estimate_gas({'from': account.address}) * 1.5)  # Увеличиваем лимит газа на 50%

    transaction = token_contract.functions.transfer(
        to_address,
        balance
    ).build_transaction({
        'chainId': web3.eth.chain_id,
        'gas': gas_limit,
        'gasPrice': gas_price,
        'nonce': nonce
    })

    signed_txn = web3.eth.account.sign_transaction(transaction, private_key=private_key)
    txn_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)
    return txn_hash.hex()

# Функция для обработки аккаунта
def process_account(i, private_key, sub_account, proxies, total_keys):
    spinner = cycle(['|', '/', '-', '\\'])
    account = Account.from_key(private_key)
    wallet_address = account.address
    user_data = get_user_data(wallet_address, proxies)
    allocation = user_data['allocations'][0]
    index = int(allocation['merkleIndex'])
    amount = int(allocation['tokenAmount'])
    merkle_proof = allocation['merkleProof']

    expiry = int(time.time()) + 3600  # Текущие время + 1 час
    message = encode_defunct(text=f'{wallet_address}:{expiry}')
    signature = web3.eth.account.sign_message(message, private_key=private_key).signature.hex()

    current_time = datetime.now()
    print(
        f'{current_time.date()} {current_time.time()} | [{i}/{total_keys}] | {wallet_address} | Claim {amount / 10 ** 18} ZKS success')

    txn_hash = send_claim_transaction(web3, index, amount, merkle_proof, wallet_address, expiry, signature, private_key)
    print(
        f'{current_time.date()} {current_time.time()} | [{i}/{total_keys}] | {wallet_address} | Claim transaction sent: {txn_hash}')

    while True:
        balance = check_token_balance(web3, wallet_address)
        if balance > 0:
            if SEND_EXCHANGE:
                current_time = datetime.now()
                print(
                    f'{current_time.date()} {current_time.time()} | [{i}/{total_keys}] | {wallet_address} | Sent {balance / 10 ** 6} ZKS from {wallet_address} to {sub_account}')
                txn_hash = send_tokens(web3, private_key, sub_account, balance)
                print(
                    f'{current_time.date()} {current_time.time()} | [{i}/{total_keys}] | {wallet_address} | Tokens sent: {txn_hash}')
            break
        else:
            current_time = datetime.now()
            print(
                f'{current_time.date()} {current_time.time()} | [{i}/{total_keys}] | {wallet_address} | Waiting tokens... {next(spinner)}',
                end='\r')
        time.sleep(0.1)

# Основная функция
def main():
    proxies = load_proxies(PROXY_FILE_PATH)
    private_keys = load_private_keys(KEYS_FILE_PATH)
    sub_accounts = load_sub_accounts(SUB_ACCS_FILE_PATH)

    total_keys = len(private_keys)

    with ThreadPoolExecutor(max_workers=POTOK) as executor:
        for i, (private_key, sub_account) in enumerate(zip(private_keys, sub_accounts), start=1):
            executor.submit(process_account, i, private_key, sub_account, proxies, total_keys)

if __name__ == '__main__':
    main()