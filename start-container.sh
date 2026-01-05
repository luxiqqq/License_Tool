#!/bin/bash
set -e

# Funzione per estrarre il link di auth dal JSON
get_auth_url() {
    echo "$1" | python3 -c "import sys, json; print(json.load(sys.stdin).get('signin_url', ''))"
}

# ==============================================================================
# 1. AVVIO OLLAMA
# ==============================================================================
echo "🔴 Starting Ollama server..."
ollama serve &

# Aspettiamo che la porta sia aperta
echo "⏳ Waiting for Ollama startup..."
until curl -s http://127.0.0.1:11434/api/version > /dev/null; do
    sleep 1
done
echo "✅ Ollama is active!"

# ==============================================================================
# 2. SELEZIONE E PULL DEL MODELLO
# ==============================================================================
# Determina quale modello usare (priorità al Cloud)
MODEL_TO_USE=${OLLAMA_GENERAL_MODEL:-$OLLAMA_CODING_MODEL}

echo "📦 Ensuring model '$MODEL_TO_USE' is available..."
# Facciamo il PULL preventivo. Se è un modello cloud, scaricherà solo il manifesto (veloce).
ollama pull "$MODEL_TO_USE"

# ==============================================================================
# 3. CONTROLLO AUTORIZZAZIONE (BLOCCANTE)
# ==============================================================================
# Eseguiamo questo controllo solo se è un modello "-cloud"
if [[ "$MODEL_TO_USE" == *"-cloud" ]]; then
    echo "☁️  Verifying authorization for Cloud Model..."

    # Facciamo la richiesta di test. Usiamo "|| true" per evitare crash se riceviamo errori 401/500
    RESPONSE=$(curl -s -X POST http://127.0.0.1:11434/api/generate -d "{\"model\": \"$MODEL_TO_USE\", \"prompt\": \"hi\", \"stream\": false}" || true)

    # Controlliamo se la risposta contiene "unauthorized"
    if echo "$RESPONSE" | grep -q "unauthorized"; then

        # Estraiamo il link
        AUTH_URL=$(get_auth_url "$RESPONSE")

        echo ""
        echo "🚨 ======================================================= 🚨"
        echo "   AUTORIZZAZIONE RICHIESTA PER OLLAMA CLOUD"
        echo "   Il container è in pausa finché non autorizzi questo dispositivo."
        echo "   ======================================================="
        echo ""
        echo "👉  CLICCA QUESTO LINK E PREMI 'AUTHORIZE':"
        echo "    $AUTH_URL"
        echo ""
        echo "⏳ In attesa di autorizzazione..."

        # CICLO DI ATTESA INFINITO (Blocca l'avvio di Python)
        # Continua a provare ogni 5 secondi finché "unauthorized" sparisce
        while echo "$RESPONSE" | grep -q "unauthorized"; do
            sleep 5
            RESPONSE=$(curl -s -X POST http://127.0.0.1:11434/api/generate -d "{\"model\": \"$MODEL_TO_USE\", \"prompt\": \"hi\", \"stream\": false}" || true)
        done

        echo "✅ Autorizzazione Rilevata! Sblocco in corso..."
    else
        echo "✅ Il modello è già autorizzato e pronto all'uso."
    fi
fi

# ==============================================================================
# 4. AVVIO BACKEND PYTHON
# ==============================================================================
echo "🚀 Starting FastAPI Backend..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload