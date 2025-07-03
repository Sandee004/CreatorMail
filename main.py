from flask import Flask, request, jsonify, session
import requests
from web3 import Web3
from cryptography.fernet import Fernet
import base64
import hashlib
import os
from flasgger import Swagger
from eth_account import Account
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from flask_migrate import Migrate

# ERC20 ABI for token contract interaction
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "name",
        "outputs": [{"name": "", "type": "string"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_from", "type": "address"},
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transferFrom",
        "outputs": [{"name": "", "type": "bool"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"}
        ],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "remaining", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "owner", "type": "address"},
            {"indexed": True, "name": "spender", "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"}
        ],
        "name": "Approval",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"}
        ],
        "name": "Transfer",
        "type": "event"
    }
]


app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///wallet.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = os.getenv("FLASK_SECRET_KEY")

db = SQLAlchemy(app)
swagger = Swagger(app)
migrate = Migrate(app, db)

Account.enable_unaudited_hdwallet_features()


class Wallet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    wallet_address = db.Column(db.String(42), nullable=False)
    encrypted_private_key = db.Column(db.Text, nullable=False)


class TokenList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), nullable=False, unique=True)
    contract_address = db.Column(db.String(100), nullable=False, unique=True)

    def __repr__(self):
        return f"<Token {self.symbol}>"


def encrypt_data(data, passphrase):
    print(f"[DEBUG] Encrypting data: {data}")
    key = hashlib.sha256(passphrase.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key[:32])
    fernet = Fernet(fernet_key)
    encrypted_data = fernet.encrypt(data.encode())
    print(f"[DEBUG] Encrypted data: {encrypted_data}")
    return encrypted_data


def decrypt_data(encrypted_data, passphrase):
    print(f"[DEBUG] Decrypting data: {encrypted_data}")
    key = hashlib.sha256(passphrase.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key[:32])
    fernet = Fernet(fernet_key)
    decrypted_data = fernet.decrypt(encrypted_data).decode()
    print(f"[DEBUG] Decrypted data: {decrypted_data}")
    return decrypted_data


def get_web3():
    CREATOR_CHAIN_RPC_URL = "https://rpc.creatorchain.io/"
    w3 = Web3(Web3.HTTPProvider(CREATOR_CHAIN_RPC_URL))
    if not w3.is_connected():
        print("[ERROR] Web3 connection failed.")
    else:
        print("[DEBUG] Web3 connected successfully.")
    return w3



@app.route("/")
def home():
    return "Home"


@app.route('/create_wallet', methods=['POST'])
def create_wallet():
    """
    Create a new Ethereum wallet with a seed phrase
    ---
    tags:
      - Wallet
    consumes:
      - application/json
    parameters:
      - name: body
        in: body
        required: true
        description: JSON object containing PIN and Username
        schema:
          type: object
          properties:
            pin:
              type: string
              example: "1234"
              description: "PIN for encrypting the private key"
            username:
              type: string
              example: "johnny"
              description: "Unique username for the wallet"
    responses:
      200:
        description: Wallet created successfully
        schema:
          type: object
          properties:
            address:
              type: string
              description: Ethereum wallet address
            encrypted_private_key:
              type: string
              description: Encrypted private key
            seed_phrase:
              type: string
              description: Seed phrase for wallet recovery
            username:
              type: string
              description: Username associated with the wallet
      400:
        description: Error in request data
    """

    pin = request.json.get('pin')
    username = request.json.get('username')
    print(f"[DEBUG] Received PIN: {pin}")
    print(f"[DEBUG] Received username: {username}")
    
    if not pin:
        return jsonify({'error': 'PIN is required'}), 400

    if not username:
      return jsonify({'error': 'Username is required'}), 400
    
    existing_user = Wallet.query.filter_by(username=username).first()
    if existing_user:
        return jsonify({'error': 'Username should be unique.'}), 400

    mnemonic = Account.create_with_mnemonic()

    #w3 = Web3(Web3.EthereumTesterProvider())
    w3 = get_web3()
    account = Account.from_mnemonic(mnemonic[1])
    wallet_address = account.address
    private_key = account.key.hex()
    
    print(f"[DEBUG] Generated mnemonic: {mnemonic[1]}")
    print(f"[DEBUG] Generated wallet address: {wallet_address}")
    print(f"[DEBUG] Generated private key: {private_key}")
    print(f"[DEBUG] Generated username: {username}")
    
    encrypted_private_key = encrypt_data(private_key, pin)
    
    new_wallet = Wallet(
        username=username,
        wallet_address=wallet_address,
        encrypted_private_key=encrypted_private_key.decode()
    )
    db.session.add(new_wallet)
    db.session.commit()

    return jsonify({
        'address': wallet_address,
        'seed_phrase': mnemonic[1],
        'username': username
    })


@app.route('/decrypt_wallet', methods=['POST'])
def decrypt_wallet():
    """
    Decrypt wallet using the Username and PIN
    ---
    tags:
      - Wallet
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            username:
              type: string
              example: "johnny"
              description: "Username associated with the wallet"
            pin:
              type: string
              example: "1234"
              description: "PIN for decrypting the private key"
    responses:
      200:
        description: "Decryption successful"
        schema:
          type: object
          properties:
            private_key:
              type: string
              description: "Decrypted private key"
      400:
        description: "Invalid request or decryption failed"
      404:
        description: "Wallet not found"
    """
    username = request.json.get('username')
    pin = request.json.get('pin')

    print(f"[DEBUG] Received Username: {username}")
    print(f"[DEBUG] Received PIN: {pin}")
    
    if not username:
        return jsonify({'error': 'Username is required'}), 400
    
    if not pin:
        return jsonify({'error': 'PIN is required'}), 400

    wallet = Wallet.query.filter_by(username=username).first()

    if not wallet:
        return jsonify({'error': 'Wallet not found'}), 404

    encrypted_private_key = wallet.encrypted_private_key
    print(f"[DEBUG] Fetched Encrypted Private Key: {encrypted_private_key}")

    try:
        decrypted_private_key = decrypt_data(encrypted_private_key, pin)
        return jsonify({'private_key': decrypted_private_key})
    except Exception as e:
        print(f"[ERROR] Decryption failed: {str(e)}")
        return jsonify({'error': 'Invalid PIN or corrupted data'}), 400


@app.route('/import_wallet', methods=['POST'])
def import_wallet():
    """
    Import an existing wallet using a private key and associate it with a username
    ---
    tags:
      - Wallet
    consumes:
      - application/json
    parameters:
      - name: body
        in: body
        required: true
        description: JSON object containing PIN, Private Key, and Username
        schema:
          type: object
          properties:
            pin:
              type: string
              example: "1234"
              description: "PIN for encrypting the private key"
            private_key:
              type: string
              example: "0xYOUR_PRIVATE_KEY"
              description: "The private key to import the wallet"
            username:
              type: string
              example: "john_doe"
              description: "Unique username to associate with the wallet"
    responses:
      200:
        description: Wallet imported successfully
        schema:
          type: object
          properties:
            message:
              type: string
            address:
              type: string
      400:
        description: Error in request data
    """
# Get request data
    pin = request.json.get('pin')
    private_key = request.json.get('private_key')
    username = request.json.get('username')

    print(f"[DEBUG] Received PIN: {pin}")
    print(f"[DEBUG] Received Private Key: {private_key}")
    print(f"[DEBUG] Received Username: {username}")

    # Validate input fields
    if not pin:
        return jsonify({'error': 'PIN is required'}), 400
    if not private_key:
        return jsonify({'error': 'Private key is required'}), 400
    if not username:
        return jsonify({'error': 'Username is required'}), 400

    try:
        # Check if username is already taken
        existing_wallet = Wallet.query.filter_by(username=username).first()
        if existing_wallet:
            return jsonify({'error': 'Username should be unique'}), 400

        # Import wallet using private key
        w3 = get_web3()
        account = w3.eth.account.from_key(private_key)
        wallet_address = account.address
        
        print(f"[DEBUG] Imported Wallet Address: {wallet_address}")
        
        # Encrypt private key with PIN
        encrypted_private_key = encrypt_data(private_key, pin)
        
        # Save to database
        new_wallet = Wallet(
            username=username,
            wallet_address=wallet_address,
            encrypted_private_key=encrypted_private_key.decode()
        )
        db.session.add(new_wallet)
        db.session.commit()

        return jsonify({
            'message': 'Wallet imported successfully',
            'address': wallet_address
        }), 200

    except Exception as e:
        print(f"[ERROR] Import failed: {str(e)}")
        return jsonify({'error': 'Invalid private key', 'details': str(e)}), 400


@app.route('/import_wallet_from_seed', methods=['POST'])
def import_wallet_from_seed():
    """
    Import an existing wallet using a seed phrase and associate it with a username
    ---
    tags:
      - Wallet
    consumes:
      - application/json
    parameters:
      - name: body
        in: body
        required: true
        description: JSON object containing PIN, Seed Phrase, and Username
        schema:
          type: object
          properties:
            pin:
              type: string
              example: "1235"
              description: "PIN for encrypting the private key"
            seed_phrase:
              type: string
              example: "awesome flush album dress laugh slab exhaust odor region pupil place artist"
              description: "The seed phrase for wallet recovery"
            username:
              type: string
              example: "johnny"
              description: "Unique username for the wallet"
    responses:
      200:
        description: Wallet imported and saved successfully
        schema:
          type: object
          properties:
            message:
              type: string
            address:
              type: string
      400:
        description: Error in request data
    """
    try:
        data = request.get_json(force=True)
        print(f"[DEBUG] Parsed JSON: {data}")

        pin = data.get('pin')
        seed_phrase = data.get('seed_phrase')
        username = data.get('username')
        
        print(f"[DEBUG] Received PIN: {pin}")
        print(f"[DEBUG] Received Seed Phrase: {seed_phrase}")
        print(f"[DEBUG] Received Username: {username}")

        if not pin or not seed_phrase or not username:
            return jsonify({'error': 'PIN, seed phrase, and username are required'}), 400

        # Validate seed phrase length
        words = seed_phrase.split()
        print(f"[DEBUG] Seed Phrase Word Count: {len(words)} - Words: {words}")
        if len(words) not in [12, 15, 18, 21, 24]:
            return jsonify({'error': 'Invalid seed phrase length'}), 400

        try:
            account = Account.from_mnemonic(seed_phrase)
            wallet_address = account.address
            private_key = account.key.hex()
            print(f"[DEBUG] Derived Address: {wallet_address}")
            print(f"[DEBUG] Derived Private Key: {private_key}")
        except Exception as e:
            print(f"[ERROR] Seed phrase derivation failed: {str(e)}")
            return jsonify({'error': 'Invalid seed phrase'}), 400
        
        # Encrypt private key
        encrypted_private_key = encrypt_data(private_key, pin)

        # Check if username is already taken
        existing_wallet = Wallet.query.filter_by(username=username).first()
        if existing_wallet:
            return jsonify({'error': 'Username is already taken'}), 400

        # Save to database
        new_wallet = Wallet(
            username=username,
            wallet_address=wallet_address,
            encrypted_private_key=encrypted_private_key.decode()
        )
        db.session.add(new_wallet)
        db.session.commit()

        return jsonify({
            'message': 'Wallet imported and saved successfully',
            'address': wallet_address
        }), 200

    except Exception as e:
        print(f"[ERROR] Import failed: {str(e)}")
        return jsonify({'error': 'Invalid request or seed phrase'}), 400


@app.route('/check_username', methods=['POST'])
def check_username():
    """
    Check if the username exists in the database
    ---
    tags:
      - Wallet
    consumes:
      - application/json
    parameters:
      - name: body
        in: body
        required: true
        description: JSON object containing the Username to check
        schema:
          type: object
          properties:
            username:
              type: string
              example: "johnny"
              description: "Username to check for existence"
    responses:
      200:
        description: Username validation result
        schema:
          type: object
          properties:
            exists:
              type: boolean
              description: True if the username is taken, False otherwise
      400:
        description: Error in request data
    """
    username = request.json.get('username')
    print(f"[DEBUG] Checking username: {username}")

    if not username:
        return jsonify({'error': 'Username is required'}), 400

    # Check if the username exists in the database
    user_exists = Wallet.query.filter_by(username=username).first() is not None
    
    return jsonify({'exists': user_exists}), 200


@app.route('/send_token', methods=['POST'])
def send_token():
    """
    Send tokens to another user's wallet
    ---
    tags:
      - Wallet
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            sender_username:
              type: string
              example: "johnny"
              description: "Sender's username associated with the wallet"
            pin:
              type: string
              example: "1234"
              description: "PIN for decrypting the private key"
            receiver_creator_username:
              type: string
              example: "gideonjones"
              description: "Receiver's creator username to resolve wallet address"
            token:
              type: string
              example: "USDC"
              description: "Token symbol to send"
            amount:
              type: string
              example: "20"
              description: "Amount to send"
          required:
            - sender_username
            - pin
            - receiver_creator_username
            - token
            - amount
    responses:
      200:
        description: "Token sent successfully"
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Token sent successfully"
            transaction_hash:
              type: string
              example: "0xabc123..."
      400:
        description: "Error in request data"
        schema:
          type: object
          properties:
            error:
              type: string
              example: "All fields are required"
      404:
        description: "Receiver or sender address not found"
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Receiver address not found"
      500:
        description: "Token transfer failed"
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Token transfer failed"
            details:
              type: string
              example: "Insufficient token balance"
    """

    data = request.get_json(force=True)
    sender_username = data.get('sender_username')
    pin = data.get('pin')
    receiver_creator_username = data.get('receiver_creator_username')
    token_symbol = data.get('token')
    amount = data.get('amount')
    
    print(f"[DEBUG] Received PIN: {pin}")
    print(f"[DEBUG] Receiver Username: {receiver_creator_username}")
    print(f"[DEBUG] Token: {token_symbol}")
    print(f"[DEBUG] Amount: {amount}")

    # Validate input fields
    if not pin or not receiver_creator_username or not token_symbol or not amount:
        return jsonify({'error': 'All fields are required'}), 400

    try:
        # Resolve receiver's wallet address using the API
        receiver_api_url = f"https://zns.bio/api/resolveDomain?chain=66665&domain={receiver_creator_username}"
        print(f"[DEBUG] Resolving receiver domain using URL: {receiver_api_url}")

        receiver_response = requests.get(receiver_api_url)
        if receiver_response.status_code != 200:
            print("[ERROR] Failed to resolve receiver domain.")
            return jsonify({'error': 'Failed to resolve receiver address'}), 400
        
        receiver_data = receiver_response.json()
        receiver_address = receiver_data.get('address')
        
        if not receiver_address:
            print("[ERROR] Receiver address not found in API response.")
            return jsonify({'error': 'Receiver address not found'}), 404
        
        print(f"[DEBUG] Receiver Wallet Address: {receiver_address}")

        # Get token contract details
        token = TokenList.query.filter_by(symbol=token_symbol).first()
        if not token:
            return jsonify({'error': 'Invalid token symbol'}), 400

        contract_address = token.contract_address
        print(f"[DEBUG] Contract Address: {contract_address}")

        # Resolve sender's wallet address using the API
        # Get username from session
        if not sender_username:
            print("[ERROR] No username gotten. Pls try again later.")
            return jsonify({'error': 'User not authenticated'}), 401

        sender_api_url = f"https://zns.bio/api/resolveDomain?chain=66665&domain={sender_username}"
        print(f"[DEBUG] Resolving sender domain using URL: {sender_api_url}")

        sender_response = requests.get(sender_api_url)
        if sender_response.status_code != 200:
            print("[ERROR] Failed to resolve sender domain.")
            return jsonify({'error': 'Failed to resolve sender address'}), 400
        
        sender_data = sender_response.json()
        sender_address = sender_data.get('address')
        
        if not sender_address:
            print("[ERROR] Sender address not found in API response.")
            return jsonify({'error': 'Sender address not found'}), 404
        
        print(f"[DEBUG] Sender Wallet Address: {sender_address}")

        # Get sender's wallet details from DB (only for private key)
        sender_wallet = Wallet.query.filter_by(username=sender_username).first()
        if not sender_wallet:
            print(f"[ERROR] No wallet found for username: {sender_username}")
            return jsonify({'error': 'Sender wallet not found'}), 404

        encrypted_private_key = sender_wallet.encrypted_private_key
        if not encrypted_private_key:
            print("[ERROR] Sender wallet has no private key.")
            return jsonify({'error': 'Sender private key not found'}), 404
        
        # Decrypt private key
        decrypted_private_key = decrypt_data(encrypted_private_key.encode(), pin)
        w3 = get_web3()

        # Check if the token is CETH (native token)
        if token_symbol == "CETH":
            print("[INFO] CETH detected. Sending native token.")

            # Convert the amount to Wei (smallest unit for Ethereum)
            amount_in_wei = w3.to_wei(amount, 'ether')
            print(f"[DEBUG] Amount in Wei: {amount_in_wei}")

            # Check sender's native balance
            sender_balance = w3.eth.get_balance(sender_address)
            print(f"[DEBUG] Sender's CETH Balance: {sender_balance}")

            if sender_balance < amount_in_wei:
                return jsonify({'error': 'Insufficient CETH balance'}), 400

            # Get the latest nonce for the sender's address
            nonce = w3.eth.get_transaction_count(sender_address, 'pending')

            # Build the transaction for native token transfer
            tx = {
                'chainId': 66665,
                'to': receiver_address,
                'value': amount_in_wei,
                'gas': 21000,
                'gasPrice': w3.to_wei('5', 'gwei'),
                'nonce': nonce
            }

            # Sign the transaction and send
            signed_tx = w3.eth.account.sign_transaction(tx, private_key=decrypted_private_key)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            print(f"[DEBUG] CETH Transaction Hash: {tx_hash.hex()}")

            return jsonify({'message': 'CETH sent successfully', 'transaction_hash': tx_hash.hex()}), 200

        else:
            # For ERC-20 tokens, continue with the contract logic
            contract = w3.eth.contract(address=contract_address, abi=ERC20_ABI)

            # Get token decimals
            decimals = contract.functions.decimals().call()
            print(f"[DEBUG] Token Decimals: {decimals}")

            # Convert human-readable amount to smallest unit
            amount_in_smallest_unit = int(float(amount) * (10 ** decimals))
            print(f"[DEBUG] Amount in smallest unit: {amount_in_smallest_unit}")

            # Check sender's token balance in smallest unit
            sender_balance = contract.functions.balanceOf(sender_address).call()
            print(f"[DEBUG] Sender's Token Balance: {sender_balance}")

            if sender_balance < amount_in_smallest_unit:
                return jsonify({'error': 'Insufficient token balance'}), 400

            # Get the latest nonce for the sender's address
            nonce = w3.eth.get_transaction_count(sender_address, 'pending')

            # Create the transaction for ERC-20 transfer
            tx = contract.functions.transfer(receiver_address, amount_in_smallest_unit).build_transaction({
                'chainId': 66665,
                'gas': 200000,
                'gasPrice': w3.to_wei('5', 'gwei'),
                'nonce': nonce
            })

            # Sign the transaction and send
            signed_tx = w3.eth.account.sign_transaction(tx, private_key=decrypted_private_key)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            print(f"[DEBUG] ERC-20 Transaction Hash: {tx_hash.hex()}")

            return jsonify({'message': 'Token sent successfully', 'transaction_hash': tx_hash.hex()}), 200

    except Exception as e:
        print(f"[ERROR] Token transfer failed: {str(e)}")
        return jsonify({'error': 'Token transfer failed', 'details': str(e)}), 500


@app.route("/get_tokens", methods=["GET"])
def get_token_symbols():
    """
    Get list of all token symbols
    ---
    tags:
      - Tokens
    responses:
      200:
        description: List of all token symbols
        schema:
          type: object
          properties:
            message:
              type: string
              example: "List of token symbols retrieved successfully"
            data:
              type: array
              items:
                type: string
              example:
                - "ETH"
                - "USDT"
                - "USDC"
                - "DAI"
      500:
        description: Internal server error
    """
    try:
        tokens = TokenList.query.all()
        token_symbols = [token.symbol for token in tokens]
        print(token_symbols)
        return jsonify({
            "message": "List of token symbols retrieved successfully",
            "data": token_symbols
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get_token_balances', methods=['POST'])
def get_token_balances():
    """
    Get token balances for a wallet based on the provided username
    ---
    tags:
      - Wallet
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            username:
              type: string
              example: "johnny"
              description: "Username associated with the wallet"
    responses:
      200:
        description: Token balances for the wallet
        schema:
          type: object
          properties:
            balances:
              type: object
              additionalProperties:
                type: string
              example:
                USDT: "5.0"
                USDC: "2.0"
      400:
        description: "Username is required or user must be logged in"
      404:
        description: "Wallet not found"
      500:
        description: "Internal server error"
    """
    try:
        data = request.get_json(force=True)
        username = data.get('username')
        print(f"[DEBUG] Checking token balances for username: {username}")

        if not username:
            return jsonify({'error': 'Username is required or user must be logged in'}), 400

        
        wallet = Wallet.query.filter_by(username=username).first()
        if not wallet:
            return jsonify({'error': 'Wallet not found'}), 404

        wallet_address = wallet.wallet_address
        print(f"[DEBUG] Wallet Address: {wallet_address}")

        w3 = get_web3()

        # Get all token contracts
        tokens = TokenList.query.all()
        balances = {}

        for token in tokens:
          if not token.contract_address:
              print(f"[ERROR] Token {token.symbol} has no contract address.")
              balances[token.symbol] = "No Contract Address"
              continue
    
          try:
              # Special handling for CETH as native token
              if token.contract_address == "native":
                  balance = w3.eth.get_balance(wallet_address)
                  human_readable_balance = w3.from_wei(balance, 'ether')
                  balances[token.symbol] = str(human_readable_balance)
                  print(f"[DEBUG] {token.symbol} Balance: {human_readable_balance} (Native)")
              
              else:
                  # For other ERC-20 tokens
                  contract = w3.eth.contract(address=token.contract_address, abi=ERC20_ABI)
                  balance = contract.functions.balanceOf(wallet_address).call()
                  decimals = contract.functions.decimals().call()
                  human_readable_balance = balance / (10 ** decimals)
                  balances[token.symbol] = str(human_readable_balance)
                  print(f"[DEBUG] {token.symbol} Balance: {human_readable_balance}")
            
          except Exception as e:
              print(f"[ERROR] Failed to get balance for {token.symbol}: {str(e)}")
              balances[token.symbol] = "Error"

        return jsonify({'balances': balances}), 200

    except Exception as e:
        print(f"[ERROR] Token balance check failed: {str(e)}")
        return jsonify({'error': 'Failed to get token balances', 'details': str(e)}), 500


@app.route('/logout', methods=['POST'])
def logout():
    """
    Logout the current user
    ---
    tags:
      - Auth
    responses:
      200:
        description: Logout successful
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Logout successful"
    """
    session.clear()
    return jsonify({'message': 'Logout successful'}), 200


if __name__ == '__main__':
    with app.app_context():
        if TokenList.query.count() < 5: 
            print("[INFO] Seeding TokenList table...")

            tokens = [
                TokenList(symbol="CETH", contract_address="native"),
                TokenList(symbol="USDT", contract_address=Web3.to_checksum_address("0xb0517790d29753429d63efe95be5879edc8c3311")),
                TokenList(symbol="USDC", contract_address=Web3.to_checksum_address("0xE0870ba18492E46a8137daE711d583aae26E7337")),
                TokenList(symbol="DAI", contract_address=Web3.to_checksum_address("0xd0015150ef225d6762e8adbd682b4d7e941846d6")),
                TokenList(symbol="BTC", contract_address=Web3.to_checksum_address("0x33950C41c72D1a8c559aE312a81F9DA3e42D09D4"))
            ]

            db.session.bulk_save_objects(tokens)
            db.session.commit()
            print("[INFO] Tokens table seeded successfully for Creator Chain.")
        else:
            print("[INFO] TokenList table already populated. Skipping seeding.")

    app.run(debug=True)
