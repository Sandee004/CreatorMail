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
from flask_migrate import Migrate


app = Flask(__name__)
swagger = Swagger(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///wallet_app.db'  # Use SQLite for now
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize DB
db = SQLAlchemy(app)
migrate = Migrate(app, db)

Account.enable_unaudited_hdwallet_features()


class Tokens(db.Model):
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


@app.before_first_request
def seed_tokens():
    if Tokens.query.count() == 0:  # Only seed if empty
        tokens = [
            Tokens(symbol="USDT", contract_address="0xdAC17F958D2ee523a2206206994597C13D831ec7"),
            Tokens(symbol="USDC", contract_address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"),
            Tokens(symbol="DAI", contract_address="0x6B175474E89094C44Da98b954EedeAC495271d0F")
        ]
        db.session.bulk_save_objects(tokens)
        db.session.commit()


@app.route("/")
def home():
    return "Home"


import json

# File to store the mappings
FILE_PATH = 'user_wallets.json'

# Load data from file or initialize an empty dictionary
def load_user_wallets():
    try:
        with open(FILE_PATH, 'r') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# Save data to file
def save_user_wallets():
    with open(FILE_PATH, 'w') as file:
        json.dump(user_wallets, file, indent=4)

# Initialize the in-memory storage from file
user_wallets = load_user_wallets()


@app.route('/create_wallet', methods=['POST'])
def create_wallet():
    """
    Create a new Ethereum wallet with a seed phrase
    ---
    tags:
      - Wallet
    parameters:
      - name: pin
        in: body
        type: string
        required: true
        description: PIN for encrypting the private key
        schema:
          type: object
          properties:
            pin:
              type: string
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
    """
    pin = request.json.get('pin')
    username = request.json.get('username')
    print(f"[DEBUG] Received PIN: {pin}")
    print(f"[DEBUG] Received username: {username}")
    
    if not pin:
        return jsonify({'error': 'PIN is required'}), 400

    if not username:
      return jsonify({'error': 'Username is required'}), 400
    
    mnemonic = Account.create_with_mnemonic()

    #w3 = Web3(Web3.EthereumTesterProvider())
    INFURA_PROJECT_ID = os.getenv('INFURA_PROJECT_ID')
    INFURA_URL = f"https://mainnet.infura.io/v3/{INFURA_PROJECT_ID}"
    w3 = Web3(Web3.HTTPProvider(INFURA_URL))

    #account = w3.eth.account.create(os.urandom(32))
    account = Account.from_mnemonic(mnemonic[1])
    wallet_address = account.address
    private_key = account.key.hex()
    
    print(f"[DEBUG] Generated mnemonic: {mnemonic[1]}")
    print(f"[DEBUG] Generated wallet address: {wallet_address}")
    print(f"[DEBUG] Generated private key: {private_key}")
    print(f"[DEBUG] Generated username: {username}")
    
    encrypted_private_key = encrypt_data(private_key, pin)
    
    # Store the username and wallet address in memory and file
    user_wallets[wallet_address] = username
    save_user_wallets()  # Save to file
    print(f"[DEBUG] Updated user_wallets: {user_wallets}")

    # Store the wallet address and encrypted private key in the session
    session['wallet_address'] = wallet_address
    session['encrypted_private_key'] = encrypted_private_key.decode()

    
    return jsonify({
        'address': wallet_address,
        'seed_phrase': mnemonic[1],
        'username': username
    })


@app.route('/decrypt_wallet', methods=['POST'])
def decrypt_wallet():
    """
    Decrypt wallet using the PIN
    ---
    tags:
      - Wallet
    parameters:
      - name: pin
        in: body
        type: string
        required: true
        description: PIN for decrypting the private key
      - name: encrypted_private_key
        in: body
        type: string
        required: true
        description: The encrypted private key to be decrypted
    responses:
      200:
        description: Decryption successful
        schema:
          type: object
          properties:
            private_key:
              type: string
    """
    pin = request.json.get('pin')
    encrypted_private_key = request.json.get('encrypted_private_key')
    
    print(f"[DEBUG] Received PIN: {pin}")
    print(f"[DEBUG] Received Encrypted Private Key: {encrypted_private_key}")
    
    if not pin or not encrypted_private_key:
        return jsonify({'error': 'PIN and encrypted private key are required'}), 400
    
    try:
        decrypted_private_key = decrypt_data(encrypted_private_key.encode(), pin)
        return jsonify({'private_key': decrypted_private_key})
    except Exception as e:
        print(f"[ERROR] Decryption failed: {str(e)}")
        return jsonify({'error': 'Invalid PIN or corrupted data'}), 400


@app.route('/import_wallet', methods=['POST'])
def import_wallet():
    """
    Import an existing wallet using a private key
    ---
    tags:
      - Wallet
    parameters:
      - name: pin
        in: body
        type: string
        required: true
        description: PIN for encrypting the private key
      - name: private_key
        in: body
        type: string
        required: true
        description: The private key to import the wallet
    responses:
      200:
        description: Wallet imported successfully
        schema:
          type: object
          properties:
            address:
              type: string
            encrypted_private_key:
              type: string
    """
    pin = request.json.get('pin')
    private_key = request.json.get('private_key')
    
    print(f"[DEBUG] Received PIN: {pin}")
    print(f"[DEBUG] Received Private Key: {private_key}")
    
    if not pin:
        return jsonify({'error': 'PIN is required'}), 400

    if not private_key:
      return jsonify({"error": "Private key is required"}), 400
    
    try:
        INFURA_PROJECT_ID = os.getenv('INFURA_PROJECT_ID')
        INFURA_URL = f"https://mainnet.infura.io/v3/{INFURA_PROJECT_ID}"
        w3 = Web3(Web3.HTTPProvider(INFURA_URL))
        account = w3.eth.account.from_key(private_key)
        wallet_address = account.address
        
        print(f"[DEBUG] Imported wallet address: {wallet_address}")
        
        encrypted_private_key = encrypt_data(private_key, pin)
        
        return jsonify({
            'address': wallet_address,
            'encrypted_private_key': encrypted_private_key.decode()
        })
    except Exception as e:
        print(f"[ERROR] Import failed: {str(e)}")
        return jsonify({'error': 'Invalid private key'}), 400


@app.route('/import_wallet_from_seed', methods=['POST'])
def import_wallet_from_seed():
    """
    Import an existing wallet using a seed phrase
    ---
    tags:
      - Wallet
    consumes:
      - application/json
    parameters:
      - name: body
        in: body
        required: true
        description: JSON object containing PIN and Seed Phrase
        schema:
          type: object
          properties:
            pin:
              type: string
              example: "1235"
            seed_phrase:
              type: string
              example: "awesome flush album dress laugh slab exhaust odor region pupil place artist"
    responses:
      200:
        description: Wallet imported successfully
        schema:
          type: object
          properties:
            address:
              type: string
            encrypted_private_key:
              type: string
    """
    try:
        data = request.get_json(force=True)  # Force JSON parsing
        print(f"[DEBUG] Parsed JSON: {data}")

        pin = data.get('pin')
        seed_phrase = data.get('seed_phrase')
        
        print(f"[DEBUG] Received PIN: {pin}")
        print(f"[DEBUG] Received Seed Phrase: {seed_phrase}")

        if not pin or not seed_phrase:
            return jsonify({'error': 'PIN and seed phrase are required'}), 400

        # To check if the seed phrase is valid
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
        
        encrypted_private_key = encrypt_data(private_key, pin)

        return jsonify({
            'address': wallet_address,
            'encrypted_private_key': encrypted_private_key.decode()
        })

    except Exception as e:
        print(f"[ERROR] Import failed: {str(e)}")
        return jsonify({'error': 'Invalid request or seed phrase'}), 400



@app.route('/check_username', methods=['POST'])
def check_username():
    """
    Check if the username exists in user_wallets
    ---
    tags:
      - Wallet
    parameters:
      - name: username
        in: body
        type: string
        required: true
        description: Username to check
        schema:
          type: object
          properties:
            username:
              type: string
    responses:
      200:
        description: Username validation result
        schema:
          type: object
          properties:
            exists:
              type: boolean
    """
    username = request.json.get('username')
    print(f"[DEBUG] Checking username: {username}")

    if not username:
        return jsonify({'error': 'Username is required'}), 400

    # Check if username exists in user_wallets
    exists = username in user_wallets.values()
    return jsonify({'exists': exists})


@app.route('/send_token', methods=['POST'])
def send_token():
    """
    Send tokens to another wallet using username
    ---
    tags:
      - Wallet
    parameters:
      - name: body
        in: body
        required: true
        description: JSON object containing sender's PIN, receiver's username, token, and amount
        schema:
          type: object
          properties:
            pin:
              type: string
              example: "1234"
            username:
              type: string
              example: "receiver_username"
            token:
              type: string
              example: "USDT"
            amount:
              type: string
              example: "10"
    responses:
      200:
        description: Token sent successfully
    """
    data = request.get_json(force=True)
    pin = data.get('pin')
    receiver_username = data.get('username')
    token_symbol = data.get('token')
    amount = data.get('amount')
    
    print(f"[DEBUG] Received PIN: {pin}")
    print(f"[DEBUG] Receiver Username: {receiver_username}")
    print(f"[DEBUG] Token: {token_symbol}")
    print(f"[DEBUG] Amount: {amount}")

    if not pin or not receiver_username or not token_symbol or not amount:
        return jsonify({'error': 'All fields are required'}), 400

    # Get receiver's wallet address using username
    receiver_address = None
    for wallet, username in user_wallets.items():
        if username == receiver_username:
            receiver_address = wallet
            break
    
    if not receiver_address:
        return jsonify({'error': 'Receiver not found'}), 404

    print(f"[DEBUG] Receiver Wallet Address: {receiver_address}")

    
    token = Tokens.query.filter_by(symbol=token_symbol).first()
    if not token:
        return jsonify({'error': 'Invalid token symbol'}), 400

    contract_address = token.contract_address
    print(f"[DEBUG] Contract Address: {contract_address}")

    # Continue with Web3 interaction to send the token...
    # You'd need to:
    # 1. Decrypt the sender's private key using the PIN
    # 2. Create and sign the transaction
    # 3. Send the transaction via Web3
    
    # Decrypt sender's private key
    # Retrieve from the session
    sender_address = session.get('wallet_address')
    encrypted_private_key = session.get('encrypted_private_key')
    decrypted_private_key = decrypt_data(encrypted_private_key.encode(), pin)

# Initialize Web3
    INFURA_PROJECT_ID = os.getenv('INFURA_PROJECT_ID')
    INFURA_URL = f"https://mainnet.infura.io/v3/{INFURA_PROJECT_ID}"
    w3 = Web3(Web3.HTTPProvider(INFURA_URL))

    # Token contract instance
    contract = w3.eth.contract(address=contract_address, abi=ERC20_ABI)

# Check sender's balance
    sender_balance = contract.functions.balanceOf(sender_address).call()
    print(f"[DEBUG] Sender's Token Balance: {sender_balance}")

    if sender_balance < int(amount):
        return jsonify({'error': 'Insufficient token balance'}), 400

    # Get the latest nonce for the sender's address
    nonce = w3.eth.get_transaction_count(sender_address)

# Create the transaction
    tx = contract.functions.transfer(receiver_address, int(amount)).build_transaction({
        'chainId': 1,  # Mainnet
        'gas': 200000,
        'gasPrice': w3.to_wei('5', 'gwei'),
        'nonce': nonce
    })

    # Sign the transaction
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=decrypted_private_key)

    # Send the transaction
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    print(f"[DEBUG] Transaction Hash: {tx_hash.hex()}")

# Return the transaction hash as confirmation
    return jsonify({'message': 'Token sent successfully', 'transaction_hash': tx_hash.hex()})


    return jsonify({'message': 'Token sent successfully'})

if __name__ == '__main__':
    app.run(debug=True)




"""
def get_web3():
    INFURA_PROJECT_ID = os.getenv('INFURA_PROJECT_ID')
    INFURA_URL = f"https://mainnet.infura.io/v3/{INFURA_PROJECT_ID}"
    return Web3(Web3.HTTPProvider(INFURA_URL))
"""

