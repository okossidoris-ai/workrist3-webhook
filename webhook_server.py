"""
=============================================================
  SERVEUR PONT - TradingView Webhook → MT5
  Workrist 3 Pro - BTCUSD / XAUUSD
=============================================================
  Déployable gratuitement sur Render.com
  
  FONCTIONNEMENT :
  1. TradingView envoie un signal JSON via Webhook
  2. Ce serveur reçoit et stocke le signal
  3. Le bot MT5 interroge ce serveur toutes les secondes
  4. Si nouveau signal → MT5 exécute l'ordre
=============================================================
"""

from flask import Flask, request, jsonify
from datetime import datetime
import json
import hmac
import hashlib
import os

app = Flask(__name__)

# ─── SÉCURITÉ ───────────────────────────────────────────────
# Clé secrète pour vérifier que le signal vient bien de TradingView
# Change cette valeur et mets la même dans ton alerte TradingView
SECRET_KEY = os.environ.get("SECRET_KEY", "workrist3_secret_2026")

# ─── STOCKAGE DES SIGNAUX ───────────────────────────────────
# Dernier signal reçu par symbole
last_signals = {}
signal_history = []

# ─── ROUTE PRINCIPALE - Réception Webhook TradingView ───────
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        # Récupérer le corps de la requête
        data = request.get_json(force=True)
        
        if not data:
            return jsonify({"status": "error", "message": "Pas de données JSON"}), 400

        # Vérification clé secrète (optionnel mais recommandé)
        received_key = request.headers.get("X-Secret-Key", "")
        if received_key and received_key != SECRET_KEY:
            return jsonify({"status": "error", "message": "Clé secrète invalide"}), 403

        # Validation des champs obligatoires
        required_fields = ["action", "symbol", "price"]
        for field in required_fields:
            if field not in data:
                return jsonify({"status": "error", "message": f"Champ manquant: {field}"}), 400

        # Enrichir le signal avec timestamp
        signal = {
            "action":    data.get("action", "").upper(),   # BUY / SELL / CLOSE
            "symbol":    data.get("symbol", ""),
            "price":     float(data.get("price", 0)),
            "type":      data.get("type", "UNKNOWN"),      # RF_LONG, STRONG_LONG, etc.
            "strength":  int(data.get("strength", 1)),     # 1, 2, ou 3
            "timestamp": datetime.utcnow().isoformat(),
            "read":      False                             # Non lu par MT5
        }

        # Stocker le signal (par symbole)
        symbol = signal["symbol"]
        last_signals[symbol] = signal

        # Historique (garder les 100 derniers)
        signal_history.append(signal)
        if len(signal_history) > 100:
            signal_history.pop(0)

        print(f"✅ Signal reçu : {signal['action']} {symbol} @ {signal['price']} | Type: {signal['type']} | Force: {signal['strength']}/3")

        return jsonify({
            "status":  "success",
            "message": f"Signal {signal['action']} reçu pour {symbol}",
            "signal":  signal
        }), 200

    except Exception as e:
        print(f"❌ Erreur webhook: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── ROUTE MT5 - Récupérer le dernier signal ────────────────
@app.route("/get_signal/<symbol>", methods=["GET"])
def get_signal(symbol):
    """
    Le bot MT5 interroge cette route pour récupérer le dernier signal.
    Exemple : GET /get_signal/BTCUSD
    """
    try:
        # Chercher avec différentes variantes du symbole
        signal = None
        for key in last_signals:
            if symbol.upper() in key.upper() or key.upper() in symbol.upper():
                signal = last_signals[key]
                break

        if not signal:
            return jsonify({
                "status":  "no_signal",
                "message": f"Aucun signal pour {symbol}"
            }), 200

        # Marquer comme lu
        signal_read = dict(signal)
        last_signals[list(last_signals.keys())[0]]["read"] = True

        return jsonify({
            "status": "ok",
            "signal": signal_read
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── ROUTE MT5 - Récupérer et effacer le signal (évite les doublons) ─
@app.route("/get_signal_once/<symbol>", methods=["GET"])
def get_signal_once(symbol):
    """
    Récupère le signal UNE SEULE FOIS puis le supprime.
    Le bot MT5 utilise cette route pour éviter d'exécuter 2 fois le même signal.
    """
    try:
        signal = None
        found_key = None

        for key in last_signals:
            if symbol.upper() in key.upper() or key.upper() in symbol.upper():
                if not last_signals[key].get("read", False):
                    signal = last_signals[key]
                    found_key = key
                    break

        if not signal:
            return jsonify({
                "status":  "no_signal",
                "message": "Aucun nouveau signal"
            }), 200

        # Marquer comme lu (ne sera plus renvoyé)
        last_signals[found_key]["read"] = True

        return jsonify({
            "status": "ok",
            "signal": signal
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── ROUTE HISTORIQUE ───────────────────────────────────────
@app.route("/history", methods=["GET"])
def history():
    """Voir les 20 derniers signaux reçus"""
    return jsonify({
        "status":  "ok",
        "count":   len(signal_history),
        "signals": signal_history[-20:]
    }), 200


# ─── ROUTE STATUS ────────────────────────────────────────────
@app.route("/", methods=["GET"])
@app.route("/status", methods=["GET"])
def status():
    return jsonify({
        "status":         "running",
        "server":         "Workrist3 Webhook Bridge",
        "version":        "1.0",
        "signals_stored": len(last_signals),
        "total_received": len(signal_history),
        "timestamp":      datetime.utcnow().isoformat()
    }), 200


# ─── LANCEMENT ───────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Serveur Workrist3 démarré sur le port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
