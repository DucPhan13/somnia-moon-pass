import asyncio
import web3
from web3 import Web3
from colorama import Fore, Style, init
import pytz
from datetime import datetime
from dotenv import load_dotenv
import os

# Initialize colorama for colored output
init(autoreset=True)

# Load environment variables from .env file
load_dotenv(".env.mint")

# Configuration
RPC_URL = os.getenv("RPC_URL")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
FROM_ADDRESS = os.getenv("FROM_ADDRESS")
TO_ADDRESS = os.getenv("TO_ADDRESS")
CHAIN_ID = int(os.getenv("CHAIN_ID"), 16)  # Convert hex string to int
GAS_LIMIT = int(os.getenv("GAS_LIMIT"))
MAX_FEE_PER_GAS = int(os.getenv("MAX_FEE_PER_GAS"), 16)  # Convert hex string to int
MAX_PRIORITY_FEE_PER_GAS = int(os.getenv("MAX_PRIORITY_FEE_PER_GAS"), 16)  # Convert hex string to int
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS"))
DELAY_SECONDS = float(os.getenv("DELAY_SECONDS"))
PROXY_URL = os.getenv("PROXY_URL")  # None if not set
MIN_BALANCE_SOMI = float(os.getenv("MIN_BALANCE_SOMI"))
BASE_DATA = os.getenv("BASE_DATA")  # Base data for Level 1

# Timestamped colored logs
def log(message, color=Fore.WHITE, level="INFO"):
    utc_tz = pytz.UTC
    timestamp = datetime.now(utc_tz).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"{color}[{level}] {timestamp}{Style.RESET_ALL} {message}")

# Web3 setup
def setup_web3():
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if web3.__version__ < "6.0.0":
        raise Exception("Need web3.py 6.0.0+. Run 'pip install web3>=6.0.0'.")
    if not w3.is_connected():
        raise Exception("RPC connection failed. Check URL or network.")
    account = w3.eth.account.from_key(PRIVATE_KEY)
    if account.address.lower() != FROM_ADDRESS.lower():
        raise Exception("Private key and from address don’t match.")
    return w3, account

# Async main loop
async def main():
    try:
        w3, account = await asyncio.to_thread(setup_web3)
        log("Web3 connected, account ready. Time to mint!", Fore.GREEN)
    except Exception as e:
        log(f"Setup crashed: {e}", Fore.RED)
        return

    iteration = 0
    while iteration < MAX_ITERATIONS:
        current_data = BASE_DATA
        log(f"Iteration {iteration + 1}/{MAX_ITERATIONS}: Trying mint ...", Fore.CYAN)

        # Balance check
        try:
            balance = await asyncio.to_thread(w3.eth.get_balance, FROM_ADDRESS)
            balance_eth = w3.from_wei(balance, 'ether')
            if balance_eth < MIN_BALANCE_SOMI:
                log(f"Low balance ({balance_eth:.4f} SOMI < {MIN_BALANCE_SOMI} SOMI). Stopping.", Fore.YELLOW)
                return
            log(f"Balance: {balance_eth:.4f} SOMI. Good to go.", Fore.WHITE)
        except Exception as e:
            log(f"Balance check failed: {e}. Gracefully stopping.", Fore.RED)

        # Build tx
        try:
            transaction = {
                'from': FROM_ADDRESS,
                'to': TO_ADDRESS,
                'chainId': CHAIN_ID,
                'gas': GAS_LIMIT,
                'maxFeePerGas': MAX_FEE_PER_GAS,
                'maxPriorityFeePerGas': MAX_PRIORITY_FEE_PER_GAS,
                'nonce': await asyncio.to_thread(w3.eth.get_transaction_count, FROM_ADDRESS),
                'data': current_data
            }
        except Exception as e:
            log(f"Couldn’t build tx: {e}. Gracefully stopping.", Fore.RED)
            return

        # Gas estimate
        try:
            estimated_gas = await asyncio.to_thread(w3.eth.estimate_gas, {
                'from': FROM_ADDRESS,
                'to': TO_ADDRESS,
                'data': current_data
            })
            if estimated_gas > GAS_LIMIT:
                log(f"Gas warning: Estimate {estimated_gas} > limit {GAS_LIMIT}.", Fore.YELLOW)
        except Exception as e:
            log(f"Gas estimation failed: {e}. Gracefully stopping.", Fore.YELLOW)
            return

        # Sign tx
        try:
            signed_txn = await asyncio.to_thread(w3.eth.account.sign_transaction, transaction, PRIVATE_KEY)
        except Exception as e:
            log(f"Signing failed: {e}. Gracefully stopping.", Fore.RED)
            return

        # Send tx
        try:
            tx_hash = await asyncio.to_thread(w3.eth.send_raw_transaction, signed_txn.raw_transaction)
            log(f"Tx sent! Hash: {w3.to_hex(tx_hash)}", Fore.GREEN)

            # Wait for receipt
            receipt = await asyncio.to_thread(w3.eth.wait_for_transaction_receipt, tx_hash, timeout=300)
            log(f"Mined in block {receipt.blockNumber}", Fore.CYAN)
            if receipt.status == 1:
                log("Mint successful!", Fore.GREEN)
                iteration += 1
            else:
                log("Tx failed. Gracefully stopping.", Fore.RED)
        except Exception as e:
            log(f"Tx send failed: {e}. Gracefully stopping.", Fore.RED)
            return

        # Pause
        if iteration < MAX_ITERATIONS:
            log(f"Chilling for {DELAY_SECONDS}s...", Fore.WHITE)
            await asyncio.sleep(DELAY_SECONDS)

    if iteration >= MAX_ITERATIONS:
        log(f"Hit max iterations ({MAX_ITERATIONS}). Done!", Fore.MAGENTA)
    else:
        log("Stopped early—check errors above.", Fore.MAGENTA)

# Run it
if __name__ == "__main__":
    asyncio.run(main())