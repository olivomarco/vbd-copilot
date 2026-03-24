#!/usr/bin/env bash
# =============================================================================
# seed-demo-data.sh
# Purpose      : Seeds realistic Italian billing knowledge-base documents into
#                Blob Storage, triggers and waits for the AI Search indexer,
#                and inserts a starter Cosmos DB session + message for the
#                CUSTOMER_NAME Intelligent Bill Explainer demo.
# Usage        : RESOURCE_GROUP=<rg> SUBSCRIPTION_ID=<sub-id> ./seed-demo-data.sh
#                RESOURCE_GROUP=<rg> SUBSCRIPTION_ID=<sub-id> ./seed-demo-data.sh --cleanup
# Prerequisites: az CLI (logged in), jq, python3
#                python packages: azure-cosmos azure-identity
# Authentication: Uses az CLI credential (DefaultAzureCredential / managed
#                 identity). No access keys or connection strings are used.
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration (all overridable via environment variables)
# ---------------------------------------------------------------------------

RESOURCE_GROUP="${RESOURCE_GROUP:-}"
SUBSCRIPTION_ID="${SUBSCRIPTION_ID:-}"
RESOURCE_PREFIX="${RESOURCE_PREFIX:-CUSTOMER_NAME-bill}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
INDEXER_NAME="${INDEXER_NAME:-knowledge-base-indexer}"
COSMOS_DB_NAME="${COSMOS_DB_NAME:-billexplainer}"
COSMOS_SESSIONS_CONTAINER="${COSMOS_SESSIONS_CONTAINER:-sessions}"
COSMOS_MESSAGES_CONTAINER="${COSMOS_MESSAGES_CONTAINER:-messages}"
KNOWLEDGE_BASE_CONTAINER="knowledge-base"
CLEANUP=false
MAX_INDEXER_WAIT_SECONDS=300

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

show_help() {
  cat <<EOF
Usage: RESOURCE_GROUP=<rg> SUBSCRIPTION_ID=<sub-id> $0 [OPTIONS]

Environment variables (required):
  RESOURCE_GROUP    Azure resource group that contains the deployment
  SUBSCRIPTION_ID   Azure subscription ID

Environment variables (optional):
  RESOURCE_PREFIX   Name prefix shared by all project resources (default: CUSTOMER_NAME-bill)
  ENVIRONMENT       Deployment environment suffix (default: dev)
  INDEXER_NAME      AI Search indexer name (default: knowledge-base-indexer)
  COSMOS_DB_NAME    Cosmos DB database name (default: billexplainer)
  COSMOS_SESSIONS_CONTAINER  Cosmos container for sessions (default: sessions)
  COSMOS_MESSAGES_CONTAINER  Cosmos container for messages (default: messages)

Options:
  --cleanup   Remove all seeded demo data (blobs, Cosmos items)
  --help      Show this help message
EOF
}

for arg in "$@"; do
  case "$arg" in
    --cleanup) CLEANUP=true ;;
    --help)    show_help; exit 0 ;;
    *)         echo "ERROR: Unknown argument: $arg"; show_help; exit 1 ;;
  esac
done

# ---------------------------------------------------------------------------
# Prerequisite checks
# ---------------------------------------------------------------------------

check_prerequisites() {
  echo "--- Checking prerequisites ---"

  if [[ -z "$RESOURCE_GROUP" ]]; then
    echo "ERROR: RESOURCE_GROUP environment variable is required."
    exit 1
  fi

  if [[ -z "$SUBSCRIPTION_ID" ]]; then
    echo "ERROR: SUBSCRIPTION_ID environment variable is required."
    exit 1
  fi

  for cmd in az jq python3; do
    if ! command -v "$cmd" &>/dev/null; then
      echo "ERROR: Required command not found: $cmd"
      exit 1
    fi
  done

  if ! az account show &>/dev/null; then
    echo "ERROR: az CLI is not logged in. Run 'az login' first."
    exit 1
  fi

  az account set --subscription "$SUBSCRIPTION_ID"
  echo "Active subscription: $(az account show --query name -o tsv)"

  echo "--- Installing required Python packages ---"
  python3 -m pip install --quiet azure-cosmos azure-identity
  echo "Prerequisites OK."
}

# ---------------------------------------------------------------------------
# Derive resource names from prefix + environment
# Storage account names cannot contain hyphens; strip them.
# ---------------------------------------------------------------------------

derive_resource_names() {
  echo "--- Deriving resource names ---"

  # Strip hyphens for storage account name (Azure limitation)
  STORAGE_ACCOUNT="${RESOURCE_PREFIX//-/}storage${ENVIRONMENT}"
  SEARCH_ACCOUNT="${RESOURCE_PREFIX}-search-${ENVIRONMENT}"
  COSMOS_ACCOUNT="${RESOURCE_PREFIX}-cosmos-${ENVIRONMENT}"

  SEARCH_ENDPOINT="https://${SEARCH_ACCOUNT}.search.windows.net"
  COSMOS_ENDPOINT="https://${COSMOS_ACCOUNT}.documents.azure.com:443/"

  echo "  Storage account : $STORAGE_ACCOUNT"
  echo "  Search account  : $SEARCH_ACCOUNT"
  echo "  Cosmos account  : $COSMOS_ACCOUNT"
}

# ---------------------------------------------------------------------------
# Blob Storage - knowledge base documents
# ---------------------------------------------------------------------------

ensure_blob_container() {
  echo "--- Ensuring blob container '$KNOWLEDGE_BASE_CONTAINER' exists ---"
  CONTAINER_EXISTS=$(az storage container exists \
    --account-name "$STORAGE_ACCOUNT" \
    --name "$KNOWLEDGE_BASE_CONTAINER" \
    --auth-mode login \
    --query "exists" -o tsv)

  if [[ "$CONTAINER_EXISTS" == "true" ]]; then
    echo "Container already exists."
  else
    echo "Creating container..."
    az storage container create \
      --account-name "$STORAGE_ACCOUNT" \
      --name "$KNOWLEDGE_BASE_CONTAINER" \
      --auth-mode login \
      --output none
    echo "Container created."
  fi
}

upload_blob_if_missing() {
  local blob_name="$1"
  local content="$2"
  local tmp_file
  tmp_file="/tmp/CUSTOMER_NAME-seed-${RANDOM}.md"

  # Write content to temp file
  echo "$content" > "$tmp_file"

  local exists
  exists=$(az storage blob exists \
    --account-name "$STORAGE_ACCOUNT" \
    --container-name "$KNOWLEDGE_BASE_CONTAINER" \
    --name "$blob_name" \
    --auth-mode login \
    --query "exists" -o tsv)

  if [[ "$exists" == "true" ]]; then
    echo "  [SKIP] $blob_name already exists."
  else
    az storage blob upload \
      --account-name "$STORAGE_ACCOUNT" \
      --container-name "$KNOWLEDGE_BASE_CONTAINER" \
      --name "$blob_name" \
      --file "$tmp_file" \
      --auth-mode login \
      --output none
    echo "  [OK]   $blob_name uploaded."
  fi

  rm -f "$tmp_file"
}

seed_knowledge_base_documents() {
  echo "--- Seeding knowledge-base documents to Blob Storage ---"

  ensure_blob_container

  # ------------------------------------------------------------------
  # 1. tariff-guide-2024.md
  # ------------------------------------------------------------------
  TARIFF_GUIDE=$(cat <<'DOC'
# Guida alle Fasce Tariffarie F1, F2, F3 - Anno 2024

## Fasce orarie e loro significato

La tariffa dell'energia elettrica in Italia e' articolata in tre fasce orarie definite dall'ARERA
(Autorita' di Regolazione per Energia Reti e Ambiente). La fascia F1 comprende le ore di picco,
dal lunedi' al venerdi' dalle 08:00 alle 19:00, escluse le festivita' nazionali. In questa fascia
il costo unitario dell'energia e' piu' elevato perche' riflette la maggiore domanda sulla rete.

La fascia F2 include le ore di mezzapunta: il lunedi'-venerdi' dalle 07:00 alle 08:00 e dalle
19:00 alle 23:00, piu' il sabato dalle 07:00 alle 23:00. Il prezzo in F2 e' intermedio e
consente una certa flessibilita' nei consumi domestici. Spostare l'uso di elettrodomestici
ad alta potenza (lavatrice, lavastoviglie) in questa fascia puo' ridurre la bolletta.

La fascia F3 rappresenta le ore di bassa domanda: notte (23:00-07:00 tutti i giorni), domenica
e festivita' nazionali. Il costo dell'energia in F3 e' il piu' contenuto; e' quindi la finestra
ideale per caricare veicoli elettrici o programmare cicli lunghi degli elettrodomestici.

## Quota Potenza e Quota Energia

La bolletta elettrica comprende due componenti principali di spesa per la materia energia.
La **quota potenza** e' un costo fisso mensile calcolato in base alla potenza contrattualmente
impegnata (espressa in kW). Anche se non si consuma energia, questa quota viene addebitata.
La **quota energia** e' invece variabile e dipende dai kWh effettivamente consumati nelle
rispettive fasce F1, F2, F3. Un utilizzo consapevole delle fasce permette di ottimizzare
questa componente della bolletta.
DOC
)

  # ------------------------------------------------------------------
  # 2. bill-structure-guide.md
  # ------------------------------------------------------------------
  BILL_STRUCTURE=$(cat <<'DOC'
# Anatomia della Bolletta Energetica CUSTOMER_NAME

## Sezione 1 - Riepilogo e Importo Totale
La prima pagina della bolletta riporta il totale da pagare, la data di scadenza, il codice
cliente, il punto di fornitura (POD per l'elettricita', PDR per il gas), e il periodo di
competenza. Il saldo puo' essere effettivo (basato su lettura reale del contatore) o stimato.

## Sezione 2 - Dettaglio Consumi
In questa sezione si trovano i kWh consumati per fascia oraria (F1/F2/F3 per l'elettricita')
o i Smc (Standard metro cubo) per il gas, con le relative date di lettura. Se la lettura
e' indicata come "presunta" significa che il contatore non e' stato letto e il valore e'
calcolato sulla base dei consumi storici.

## Sezione 3 - Spesa per la Materia Energia
Comprende il costo dell'energia vera e propria: quota energia per fascia, quota potenza,
eventuale quota fissa. E' la componente su cui il mercato libero compete con il mercato
tutelato. Il prezzo e' quello del tuo contratto CUSTOMER_NAME.

## Sezione 4 - Spese per il Trasporto e la Gestione del Contatore
Questi oneri sono regolati da ARERA e sono uguali per tutti gli operatori. Comprendono
la distribuzione locale, la trasmissione nazionale e la misura del contatore.

## Sezione 5 - Oneri di Sistema
Voci stabilite dalla legge a supporto di politiche energetiche nazionali: incentivi alle
rinnovabili (A3), sostegno alle utenze in disagio (bonus), copertura dei regimi tariffari
speciali. Dal 2022 alcune di queste voci sono state azzerate o ridotte per decreto.

## Sezione 6 - Imposte
Accise sull'energia elettrica o sul gas naturale, piu' IVA (10% per usi domestici,
22% per usi non domestici sopra soglia). Le accise sono imposte fisse per kWh/Smc
indipendentemente dal prezzo di mercato.
DOC
)

  # ------------------------------------------------------------------
  # 3. faq-billing-2024.md
  # ------------------------------------------------------------------
  FAQ_BILLING=$(cat <<'DOC'
# Domande Frequenti sulla Bolletta - CUSTOMER_NAME 2024

**D: Perche' la mia bolletta e' piu' alta del solito?**
R: Le cause piu' comuni sono un aumento dei consumi stagionali (riscaldamento/raffreddamento),
una variazione del prezzo dell'energia legata ai mercati internazionali, un conguaglio dovuto
a precedenti letture stimate, o modifiche alle aliquote degli oneri di sistema.

**D: Cosa significa "conguaglio" in bolletta?**
R: Il conguaglio e' il ricalcolo dei consumi reali rispetto alle stime effettuate nelle
bollette precedenti. Se hai consumato piu' di quanto stimato pagherai la differenza;
se hai consumato meno riceverai un credito che verra' scalato dalla prossima bolletta.

**D: Come posso leggere il mio contatore?**
R: Per il contatore elettronico di seconda generazione (2G) puoi visualizzare i dati
direttamente sul display digitale. Il valore in kWh e' preceduto dalla sigla "kWh" o
"E". Puoi anche accedere all'area clienti CUSTOMER_NAME per le letture storiche.

**D: Posso richiedere una rateizzazione se non riesco a pagare?**
R: Si'. CUSTOMER_NAME offre piani di rateizzazione per bollette superiori a 50 euro con
almeno il doppio del valore della bolletta media. Contatta il servizio clienti entro
la data di scadenza per concordare un piano fino a 12 rate mensili senza interessi.

**D: Cosa e' il bonus sociale energia?**
R: E' una riduzione sulla bolletta riconosciuta automaticamente alle famiglie in
condizioni di disagio economico (ISEE sotto soglia) o in disagio fisico (uso di
apparecchiature medico-terapeutiche). Dal 2021 e' erogato in modo automatico tramite
l'INPS senza necessita' di richiesta diretta al fornitore.

**D: Come funziona il mercato libero rispetto alla tutela?**
R: Nel mercato libero come CUSTOMER_NAME scegli il prezzo e le condizioni contrattuali
con il fornitore. Nel mercato tutelato (oggi Servizio a Tutele Graduali per le PMI,
soppresso per i residenziali dal luglio 2024) il prezzo era fissato da ARERA
trimestralmente. Sul mercato libero puoi scegliere tra prezzo fisso e variabile.

**D: Il prezzo dell'energia cambiera' nella mia offerta?**
R: Dipende dal tipo di contratto. Se hai sottoscritto un'offerta a prezzo fisso il
costo al kWh rimane invariato per la durata contrattuale. Se hai un'offerta a prezzo
indicizzato (PUN o TTF) il prezzo varia mensilmente in base all'andamento dei mercati.

**D: Come posso ridurre la mia bolletta del gas?**
R: Le azioni piu' efficaci sono: abbassare la temperatura del riscaldamento di 1 grado
(risparmio stimato 5-7%), effettuare la manutenzione annuale della caldaia, installare
valvole termostatiche sui termosifoni, e spostare l'uso di acqua calda sanitaria nelle
fasce F2/F3 se hai un accumulo elettrico.
DOC
)

  # ------------------------------------------------------------------
  # 4. regulatory-charges-2024.md
  # ------------------------------------------------------------------
  REGULATORY_CHARGES=$(cat <<'DOC'
# Oneri Regolatori in Bolletta - Guida ARERA 2024

## Oneri di Sistema (OdS)

Gli oneri di sistema sono componenti tariffarie stabilite da ARERA per finanziare
obiettivi di politica energetica nazionale. Appaiono in bolletta come voci separate
e sono uguali per tutti i fornitori perche' regolati a livello nazionale.

**Componente A3 - Incentivi Fonti Rinnovabili**: Finanzia il Conto Energia e i
meccanismi di incentivazione per fotovoltaico, eolico e altre rinnovabili. E' la
componente di onere di sistema piu' rilevante in termini di importo.

**Componente MCT - Meccanismi di Compensazione Territoriale**: Ristoro ai Comuni
sede di impianti nucleari dismessi e centrali termoelettriche.

**Componente ASOS e ARIM**: Copertura del costo degli incentivi per i piccoli
impianti e gestione del sistema di misura avanzata.

## Accise

Le accise sull'energia elettrica sono imposte erariali fissate per legge. Per uso
domestico l'accisa e' pari a 0,0227 euro/kWh per i consumi fino a 1.800 kWh/anno
(residenti) e 0,0265 euro/kWh per i consumi eccedenti. Per uso non domestico
l'aliquota varia in base alla categoria d'uso.

Sul gas naturale le accise dipendono dall'utilizzo: riscaldamento domestico,
uso industriale, autotrazione. I valori sono aggiornati annualmente dalla Legge
di Bilancio.

## IVA

L'Imposta sul Valore Aggiunto si applica sull'imponibile complessivo della bolletta
(materia energia + trasporto + oneri di sistema + accise). L'aliquota e':
- 10% per le forniture domestiche di uso civile (gas e luce per la casa)
- 22% per le forniture a uso non domestico o oltre soglia di consumo
- 5% per il gas in alcune categorie agevolate (es. uso cottura cibi sotto 480 Smc/anno)
DOC
)

  # ------------------------------------------------------------------
  # 5. payment-options.md
  # ------------------------------------------------------------------
  PAYMENT_OPTIONS=$(cat <<'DOC'
# Metodi di Pagamento e Opzioni CUSTOMER_NAME

## Pagamento Diretto (RID / Addebito Diretto SEPA)

L'addebito diretto SEPA e' il sistema consigliato: la bolletta viene addebitata
automaticamente sul conto corrente alla data di scadenza. Non c'e' rischio di
dimenticare il pagamento e si evitano more o interruzioni della fornitura. Per
attivarlo accedi all'area clienti CUSTOMER_NAME e inserisci l'IBAN del conto.
L'attivazione richiede 30-45 giorni e sara' operativa dalla bolletta successiva.

## Bollettino Postale e MAV

Ogni bolletta include un bollettino postale o MAV (Mediante Avviso) pagabile presso:
uffici postali, sportelli bancari, tabaccherie aderenti al circuito PayPoint o Mooney,
e online tramite home banking inserendo il codice a barre o il codice MAV.

## Portale e App CUSTOMER_NAME

Tramite l'area clienti web o l'app mobile CUSTOMER_NAME puoi pagare con carta di credito,
carta di debito o tramite PayPal. Il pagamento e' disponibile 24 ore su 24 e viene
registrato in tempo reale. L'app invia anche notifiche push prima della scadenza.

## Rateizzazione

Per bollette di importo elevato CUSTOMER_NAME offre la possibilita' di rateizzare il
debito. Requisiti: importo minimo 50 euro, almeno il doppio della bolletta media.
Durata massima 12 rate mensili senza interessi. La richiesta va effettuata prima
della scadenza contattando il servizio clienti al numero verde o tramite chat.

## Morosita' e Sospensione Fornitura

In caso di mancato pagamento CUSTOMER_NAME invia un sollecito entro 10 giorni dalla
scadenza. Se il pagamento non avviene entro i termini di mora (ulteriori 20 giorni)
e' possibile la sospensione della fornitura. Per riattivare la fornitura e' necessario
saldare l'intero importo arretrato piu' i costi di riattivazione previsti da ARERA.
La riattivazione avviene entro 24 ore dal pagamento confermato.
DOC
)

  # Upload each document (idempotent)
  upload_blob_if_missing "tariff-guide-2024.md"       "$TARIFF_GUIDE"
  upload_blob_if_missing "bill-structure-guide.md"    "$BILL_STRUCTURE"
  upload_blob_if_missing "faq-billing-2024.md"        "$FAQ_BILLING"
  upload_blob_if_missing "regulatory-charges-2024.md" "$REGULATORY_CHARGES"
  upload_blob_if_missing "payment-options.md"         "$PAYMENT_OPTIONS"

  echo "Knowledge-base documents seeded."
}

# ---------------------------------------------------------------------------
# AI Search - trigger indexer and wait for completion
# ---------------------------------------------------------------------------

trigger_search_indexer() {
  echo "--- Triggering AI Search indexer: $INDEXER_NAME ---"

  # Acquire Azure AD token scoped to Azure AI Search
  local token
  token=$(az account get-access-token \
    --resource "https://search.azure.com" \
    --query "accessToken" -o tsv)

  local indexer_url="${SEARCH_ENDPOINT}/indexers/${INDEXER_NAME}/run?api-version=2024-07-01"

  local http_code
  http_code=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "$indexer_url" \
    -H "Authorization: Bearer $token" \
    -H "Content-Length: 0")

  if [[ "$http_code" == "202" ]]; then
    echo "Indexer run triggered (HTTP 202)."
  elif [[ "$http_code" == "409" ]]; then
    echo "Indexer is already running (HTTP 409). Will wait for current run to complete."
  else
    echo "WARNING: Unexpected HTTP response $http_code when triggering indexer. Continuing..."
  fi
}

wait_for_indexer_success() {
  echo "--- Waiting for indexer '$INDEXER_NAME' to complete (max ${MAX_INDEXER_WAIT_SECONDS}s) ---"

  local token
  local status_url="${SEARCH_ENDPOINT}/indexers/${INDEXER_NAME}/status?api-version=2024-07-01"
  local elapsed=0
  local sleep_interval=15

  while [[ $elapsed -lt $MAX_INDEXER_WAIT_SECONDS ]]; do
    token=$(az account get-access-token \
      --resource "https://search.azure.com" \
      --query "accessToken" -o tsv)

    local response
    response=$(curl -s \
      -H "Authorization: Bearer $token" \
      "$status_url")

    local last_status
    last_status=$(echo "$response" | jq -r '.lastResult.status // "unknown"')

    echo "  Indexer last result status: $last_status (${elapsed}s elapsed)"

    if [[ "$last_status" == "success" ]]; then
      echo "Indexer completed successfully."
      return 0
    elif [[ "$last_status" == "transientFailure" || "$last_status" == "persistentFailure" ]]; then
      echo "WARNING: Indexer reported failure status: $last_status"
      echo "  Error: $(echo "$response" | jq -r '.lastResult.errorMessage // "none"')"
      echo "  Continuing with demo seed despite indexer issue."
      return 0
    fi

    sleep $sleep_interval
    elapsed=$((elapsed + sleep_interval))
  done

  echo "WARNING: Indexer did not complete within ${MAX_INDEXER_WAIT_SECONDS}s. Continuing..."
}

# ---------------------------------------------------------------------------
# Cosmos DB - seed demo session and message
# ---------------------------------------------------------------------------

seed_cosmos_db() {
  echo "--- Seeding Cosmos DB demo session and message ---"

  python3 - <<PYEOF
import sys
import json
from datetime import datetime, timezone

try:
    from azure.cosmos import CosmosClient, PartitionKey
    from azure.cosmos.exceptions import CosmosResourceExistsError
    from azure.identity import DefaultAzureCredential
except ImportError as e:
    print(f"ERROR: Missing Python dependency: {e}")
    print("Run: pip install azure-cosmos azure-identity")
    sys.exit(1)

COSMOS_ENDPOINT = "${COSMOS_ENDPOINT}"
DB_NAME = "${COSMOS_DB_NAME}"
SESSIONS_CONTAINER = "${COSMOS_SESSIONS_CONTAINER}"
MESSAGES_CONTAINER = "${COSMOS_MESSAGES_CONTAINER}"

now_iso = datetime.now(timezone.utc).isoformat()

seed_session = {
    "id": "demo-session-001",
    "sessionId": "demo-session-001",
    "billRef": "IT001-2024-DEMO",
    "createdAt": now_iso,
    "ttl": 86400
}

seed_message = {
    "id": "msg-seed-001",
    "sessionId": "demo-session-001",
    "role": "assistant",
    "content": (
        "Buongiorno! Sono l'assistente virtuale di CUSTOMER_NAME. "
        "Come posso aiutarti con la tua bolletta?"
    ),
    "timestamp": now_iso,
    "ttl": 86400
}

credential = DefaultAzureCredential()
client = CosmosClient(COSMOS_ENDPOINT, credential=credential)
db = client.get_database_client(DB_NAME)

for container_name, item in [
    (SESSIONS_CONTAINER, seed_session),
    (MESSAGES_CONTAINER, seed_message),
]:
    container = db.get_container_client(container_name)
    try:
        container.create_item(body=item)
        print(f"  [OK]   Inserted item '{item['id']}' into container '{container_name}'")
    except CosmosResourceExistsError:
        print(f"  [SKIP] Item '{item['id']}' already exists in '{container_name}'")
    except Exception as ex:
        print(f"  [WARN] Could not insert into '{container_name}': {ex}")

print("Cosmos DB seeding complete.")
PYEOF
}

# ---------------------------------------------------------------------------
# Cleanup - remove seeded data only
# ---------------------------------------------------------------------------

cleanup_seeded_data() {
  echo "--- Cleaning up seeded demo data ---"

  echo "  Removing knowledge-base blobs..."
  for blob in tariff-guide-2024.md bill-structure-guide.md faq-billing-2024.md \
               regulatory-charges-2024.md payment-options.md; do
    EXISTS=$(az storage blob exists \
      --account-name "$STORAGE_ACCOUNT" \
      --container-name "$KNOWLEDGE_BASE_CONTAINER" \
      --name "$blob" \
      --auth-mode login \
      --query "exists" -o tsv 2>/dev/null || echo "false")
    if [[ "$EXISTS" == "true" ]]; then
      az storage blob delete \
        --account-name "$STORAGE_ACCOUNT" \
        --container-name "$KNOWLEDGE_BASE_CONTAINER" \
        --name "$blob" \
        --auth-mode login \
        --output none
      echo "  [OK]   Deleted blob: $blob"
    else
      echo "  [SKIP] Blob not found: $blob"
    fi
  done

  echo "  Removing Cosmos DB seed items..."
  python3 - <<PYEOF
import sys

try:
    from azure.cosmos import CosmosClient
    from azure.cosmos.exceptions import CosmosResourceNotFoundError
    from azure.identity import DefaultAzureCredential
except ImportError as e:
    print(f"WARNING: Python dependency missing, skipping Cosmos cleanup: {e}")
    sys.exit(0)

COSMOS_ENDPOINT = "${COSMOS_ENDPOINT}"
DB_NAME = "${COSMOS_DB_NAME}"

items_to_delete = [
    ("${COSMOS_SESSIONS_CONTAINER}", "demo-session-001", "demo-session-001"),
    ("${COSMOS_MESSAGES_CONTAINER}", "msg-seed-001", "demo-session-001"),
]

credential = DefaultAzureCredential()
client = CosmosClient(COSMOS_ENDPOINT, credential=credential)
db = client.get_database_client(DB_NAME)

for container_name, item_id, partition_key in items_to_delete:
    container = db.get_container_client(container_name)
    try:
        container.delete_item(item=item_id, partition_key=partition_key)
        print(f"  [OK]   Deleted item '{item_id}' from '{container_name}'")
    except CosmosResourceNotFoundError:
        print(f"  [SKIP] Item '{item_id}' not found in '{container_name}'")
    except Exception as ex:
        print(f"  [WARN] Could not delete from '{container_name}': {ex}")

print("Cosmos DB cleanup complete.")
PYEOF

  echo "Cleanup complete."
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

main() {
  echo "============================================================"
  echo " CUSTOMER_NAME Bill Explainer - Demo Data Seed Script"
  echo " Resource group : ${RESOURCE_GROUP}"
  echo " Environment    : ${ENVIRONMENT}"
  echo " Cleanup mode   : ${CLEANUP}"
  echo "============================================================"

  check_prerequisites
  derive_resource_names

  if [[ "$CLEANUP" == "true" ]]; then
    cleanup_seeded_data
  else
    seed_knowledge_base_documents
    trigger_search_indexer
    wait_for_indexer_success
    seed_cosmos_db
    echo ""
    echo "============================================================"
    echo " Demo data seeding complete."
    echo " Chat widget entry point: via Azure Front Door hostname"
    echo " Jump box access        : via Azure Bastion in the VNet"
    echo "============================================================"
  fi
}

main
