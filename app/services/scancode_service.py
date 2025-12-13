"""
This module handles the interaction with the ScanCode Toolkit CLI for raw license detection
and implements a post-processing layer using an LLM to filter false positives.
"""

import os
import json
import subprocess
import re
from re import match
from typing import List, Dict, Any, Optional, Tuple
from app.core.config import SCANCODE_BIN, OUTPUT_BASE_DIR, MINIMAL_JSON_BASE_DIR
from app.services.llm_helper import _call_ollama_gpt


#  ------------ MAIN FUNCTION TO EXECUTE SCANCODE -----------------

def run_scancode(repo_path: str) -> dict:
    """
    Executes ScanCode on the target repository and parses the JSON output.

    Note: Real-time progress is printed to the standard output.

    Args:
        repo_path (str): The file system path to the target repository.

    Returns:
        dict: The parsed JSON data from ScanCode, with the top-level
              'license_detections' key removed to reduce payload size.
    """

    # 1. Definizione degli ignore pattern (legge prima patterns_to_ignore.json)
    patterns_path = os.path.join(os.path.dirname(__file__), 'patterns_to_ignore.json')
    rules_path = os.path.join(os.path.dirname(__file__), 'license_rules.json')

    ignore_patterns = []
    if os.path.exists(patterns_path):
        with open(patterns_path, 'r', encoding='utf-8') as f:
            p = json.load(f)
        ignore_patterns = p.get("ignored_patterns", []) or []
    elif os.path.exists(rules_path):
        with open(rules_path, 'r', encoding='utf-8') as f:
            r = json.load(f)
        ignore_patterns = r.get("ignored_patterns", []) or []

    # normalizza e rimuove valori falsy
    ignore_patterns = [str(x) for x in ignore_patterns if x]

    # Assicuriamoci che la directory di output esista
    os.makedirs(OUTPUT_BASE_DIR, exist_ok=True)

    repo_name = os.path.basename(os.path.normpath(repo_path))
    output_file = os.path.join(OUTPUT_BASE_DIR, f"{repo_name}_scancode_output.json")

    # 2. Costruzione del comando base
    cmd = [
        SCANCODE_BIN,
        # Opzioni Licenza
        "--license",
        "--license-text",
        "--filter-clues",
        "--license-clarity-score",

        # Opzioni Statistiche e Classificazione
        "--tallies",
        "--tallies-key-files",
        "--classify",
    ]

    # 3. Aggiunta dinamica degli ignore pattern
    for pattern in ignore_patterns:
        cmd.extend(["--ignore", pattern])

    # 4. Aggiunta output e target
    cmd.extend([
        "--json-pp", output_file,
        repo_path,
    ])

    print(f"🚀 Avvio ScanCode su: {repo_name}")
    print(f"📂 Output su: {output_file}")

    # Real-time output (NO capture_output)
    process = subprocess.Popen(cmd)

    # Wait for completion and get return code
    returncode = process.wait()

    # Error handling according to ScanCode rules
    if returncode > 1:
        raise RuntimeError(f"Errore ScanCode (exit {returncode})")

    if returncode == 1:
        print("⚠ ScanCode ha completato con errori non fatali (exit 1).")

    if not os.path.exists(output_file):
        raise RuntimeError("ScanCode non ha generato il file JSON")

    # 1. Load the generated JSON
    with open(output_file, "r", encoding="utf-8") as f:
        scancode_data = json.load(f)

    # ⬇ Rimuovi la chiave "license_detections" dal JSON di primo livello
    # (Nota: license_detections a volte è pesante e ridondante se usi i dettagli dei file)
    scancode_data.pop("license_detections", None)

    # 2. Overwrite the file with modified data
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(scancode_data, f, indent=4, ensure_ascii=False)

    print("✅ ScanCode completato e JSON processato.")

    # 3. Ritorna i dati modificati
    return scancode_data


#  ------------ FUNCTIONS TO FILTER RESULTS WITH LLM -----------------

def remove_main_license(main_spdx, path, scancode_data) -> dict:
    """
    Removes the main license from the ScanCode results for a specific file path.
    This prevents the LLM from being biased by the main license when filtering.
    """
    for file_entry in scancode_data.get("files", []):
        for det in file_entry.get("matches", []):
            if file_entry.get("path") == path and det.get("license_spdx") == main_spdx:
                try:
                    scancode_data["files"].remove(file_entry)
                except ValueError:
                    pass

    return scancode_data

def filter_with_regex(scancode_data: dict, main_spdx: str, path: str) -> dict:
    """
    Filters ScanCode results using an LLM to remove false positives.

    It constructs a minimal JSON representation of the file matches and asks the LLM
    to validate the 'matched_text' against known license patterns.
    """
    minimal = build_minimal_json(scancode_data)
    # print(json.dumps(minimal, indent=4))
    scan_clean = remove_main_license(main_spdx, path, minimal)

    if main_spdx != "UNKNOWN":
        regex_filtered = filter_license_data(scan_clean, detected_main_spdx=True)
    else:
        regex_filtered = filter_license_data(scan_clean, detected_main_spdx=False)

    #post_regex_cleaning = remove_mainspdx_from_filespdx(regex_filtered, main_spdx)
    #return post_regex_cleaning
    return regex_filtered

def build_minimal_json(scancode_data: dict) -> dict:
    """
    Builds a minimal JSON structure from the ScanCode data.
    Instead of using the global 'license_detections' list (which requires the LLM to group),
    we iterate directly over files and collect their matches.
    """
    minimal = {"files": []}

    # Iterate over files (which have already been filtered by remove_main_license)
    for file_entry in scancode_data.get("files", []):
        path = file_entry.get("path")
        legal = file_entry.get("is_legal")
        key_file = file_entry.get("is_key_file")
        if not path:
            continue

        file_matches = []

        # ScanCode file-level detections
        for det in file_entry.get("license_detections", []):

            # 'matches' contiene i dettagli (start_line, end_line, matched_text)
            for match in det.get("matches", []):

                if match.get("from_file") == path and "LicenseRef" not in match.get("license_expression_spdx"):

                    file_matches.append({
                        "license_spdx": match.get("license_expression_spdx"),
                        "matched_text": match.get("matched_text"),
                    })

        score = file_entry.get("percentage_of_license_text")

        if file_matches:
            minimal["files"].append({
                "path": path,
                "is_legal": legal,
                "is_key_file": key_file,
                "matches": file_matches,
                "score": score
            })


    # Assicura che la cartella esista e scrive il JSON minimale invece di leggerlo
    os.makedirs(MINIMAL_JSON_BASE_DIR, exist_ok=True)
    output_minimal = os.path.join(MINIMAL_JSON_BASE_DIR, "minimal_output.json")

    with open(output_minimal, "w", encoding="utf-8") as f:
        json.dump(minimal, f, indent=4, ensure_ascii=False)

    return minimal

def filter_license_data(data: dict, detected_main_spdx: bool) -> dict:
    """
    Filtra i risultati di Scancode usando regole caricate da un file JSON esterno.
    """

    # --- 1. CARICAMENTO E COMPILAZIONE REGOLE ---

    rules_path = os.path.join(os.path.dirname(__file__), 'license_rules.json')

    if not os.path.exists(rules_path):
        raise FileNotFoundError(f"Impossibile trovare il file di regole: {rules_path}")

    with open(rules_path, 'r', encoding='utf-8') as f:
        rules = json.load(f)

    # Compiliamo le liste di esclusione in un'unica regex ottimizzata con OR logic (|)
    # Questo è molto più veloce di fare un loop su ogni stringa.
    re_references = re.compile("|".join(rules.get("ignore_patterns", [])), re.IGNORECASE)
    re_docs_changelog = re.compile("|".join(rules.get("changelog_patterns", [])), re.IGNORECASE)

    # Compiliamo la regex per il tag SPDX
    re_spdx_tag = re.compile(rules.get("spdx_tag_pattern", ""), re.IGNORECASE)

    # Compiliamo i pattern per riconoscere TESTO LEGALE EFFETTIVO delle licenze
    valid_license_patterns = []
    for pattern in rules.get("valid_license_text_patterns", []):
        try:
            valid_license_patterns.append(re.compile(pattern, re.IGNORECASE))
        except re.error:
            pass  # Skip pattern non validi

    # Compiliamo i pattern per riconoscere LINK VALIDI a licenze (RST, Markdown, URL)
    valid_link_patterns = []
    for pattern in rules.get("valid_license_link_patterns", []):
        try:
            valid_link_patterns.append(re.compile(pattern, re.IGNORECASE))
        except re.error:
            pass  # Skip pattern non validi

    # Lunghezza minima del testo
    min_text_length = rules.get("min_matched_text_length", 20)

    filtered_files = {"files": []}

    # --- 2. ELABORAZIONE ---

    files = data.get('files', [])

    for file_obj in files:
        file_path = file_obj.get('path')
        matches = file_obj.get('matches', [])
        file_score = file_obj.get('score', 0)
        legal = file_obj.get('is_legal')
        key_file = file_obj.get('is_key_file')

        if legal is True:
            filtered_files["files"].append({
                "path": file_path,
                "matches": file_obj.get('matches', []),
                "score": file_score
            })
            continue
        elif legal is False and detected_main_spdx is True and key_file is True:
            continue

        valid_matches = []

        for match in matches:
            matched_text = match.get('matched_text', '').strip()
            spdx = match.get('license_spdx', '')

            # -----------------------------------------------------------------
            # 1. VALIDAZIONE POSITIVA (WHITELIST) - La facciamo PRIMA!
            # -----------------------------------------------------------------

            is_valid_declaration = False
            match_source = None

            # A. Controllo Tag SPDX Esplicito (Priorità Massima)
            spdx_tag_hit = re_spdx_tag.search(matched_text)
            if spdx_tag_hit:
                is_valid_declaration = True
                match_source = "SPDX-TAG"

            # B. Controllo Testo Legale Boilerplate (Es. "Permission hereby granted...")
            elif not is_valid_declaration:
                for pattern_re in valid_license_patterns:
                    if pattern_re.search(matched_text):
                        is_valid_declaration = True
                        match_source = "LEGAL-TEXT"
                        break

            # C. Controllo Link Validi (Es. link a file LICENSE o URL gnu.org)
            is_valid_license_link = False
            if not is_valid_declaration:
                for pattern_re in valid_link_patterns:
                    if pattern_re.search(matched_text):
                        is_valid_license_link = True
                        is_valid_declaration = True
                        match_source = "VALID-LINK"
                        break

            # -----------------------------------------------------------------
            # 2. FILTRO NEGATIVO (BLACKLIST) - Solo se non è già validato
            # -----------------------------------------------------------------

            # Se il testo è GIA' riconosciuto come valido (es. License :: OSI Approved),
            # SALTIAMO i controlli di ignoranza.
            if not is_valid_declaration:

                # Lunghezza minima
                if len(matched_text) < min_text_length:
                    continue

                # Scarta Riferimenti/Link generici
                # Qui è dove "License ::" veniva ucciso dal regex "^license:"
                if len(matched_text) < 300:
                    if re_references.search(matched_text):
                        continue

                # Scarta Linguaggio da Changelog
                if re_docs_changelog.search(matched_text):
                    continue

            # -----------------------------------------------------------------
            # 3. FILTRO FINALE ("Zero Trust")
            # -----------------------------------------------------------------

            # Se dopo tutto questo non è una dichiarazione valida, scarta.
            if not is_valid_declaration:
                continue

                # -----------------------------------------------------------------
            # 4. ASSEGNAZIONE ID SPDX FINALE
            # -----------------------------------------------------------------

            final_spdx = None

            # Verifica validità formale ID Scancode
            scancode_id_ok = False
            if spdx and "unknown" not in spdx.lower() and "scancode" not in spdx.lower():
                scancode_id_ok = True

            # Caso 1: Tag SPDX Esplicito
            if spdx_tag_hit:
                final_spdx = spdx_tag_hit.group(1) or spdx_tag_hit.group(3)

            # Caso 2: Scancode ID valido
            if not final_spdx and scancode_id_ok:
                final_spdx = spdx

            # Caso 3: Fallback
            if not final_spdx:
                final_spdx = "LicenseRef-scancode-unknown"

            if final_spdx:
                valid_matches.append({
                    "license_spdx": final_spdx.strip(),
                    "matched_text": matched_text
                })

        # Salvataggio se ci sono match validi e score sufficiente
        if valid_matches:
            filtered_files["files"].append({
                "path": file_path,
                "matches": valid_matches,
                "score": file_score
            })

    # --- 3. OUTPUT FILE ---
    # Definisci MINIMAL_JSON_BASE_DIR nel tuo codice globale o passalo come argomento se serve
    # Qui assumo esista nel contesto o uso una default locale
    base_dir = globals().get('MINIMAL_JSON_BASE_DIR', './output')
    os.makedirs(base_dir, exist_ok=True)
    output_minimal = os.path.join(base_dir, "filtered_output.json")

    with open(output_minimal, "w", encoding="utf-8") as f:
        json.dump(filtered_files, f, indent=4, ensure_ascii=False)

    return filtered_files

#  ------------ FUNZIONI PER RILEVARE LA LICENZA PRINCIPALE DAL JSON SCANCODE -----------------

def _is_valid(value: Optional[str]) -> bool:
    """Verifies if a string is a valid SPDX and not None/empty/UNKNOWN."""
    return bool(value) and value != "UNKNOWN"

def _extract_first_valid_spdx(entry: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    """
    Returns the first valid SPDX found in the ScanCode entry,
    searching in the detected expression, license_detections, and finally in licenses.

    Returns: (spdx_expression, path) or None.
    """
    if not isinstance(entry, dict):
        return None

    path = entry.get("path") or ""

    # 1. Check main detected license expression
    spdx = entry.get("detected_license_expression_spdx")
    if _is_valid(spdx):
        return spdx, path

    # 2. Check individual detections
    # Although the root output 'license_detections' may be removed,
    # this key is still present inside each 'files' object.
    for detection in entry.get("license_detections", []) or []:
        det_spdx = detection.get("license_expression_spdx")
        if _is_valid(det_spdx):
            return det_spdx, path

    # 3. Check SPDX keys in detailed licenses
    for lic in entry.get("licenses", []) or []:
        spdx_key = lic.get("spdx_license_key")
        if _is_valid(spdx_key):
            return spdx_key, path

    return None

def _pick_best_spdx(entries: List[Dict[str, Any]]) -> Optional[Tuple[str, str]]:
    """
    Sorts files closest to root (lower path depth) and
    returns the first valid SPDX license found.

    Returns: (spdx_expression, path) or None.
    """
    if not entries:
        return None

    # Sort: use path depth (count of "/") as key
    # Lower count means closer to root.
    sorted_entries = sorted(entries, key=lambda e: (e.get("path", "") or "").count("/"))

    for entry in sorted_entries:
        res = _extract_first_valid_spdx(entry)
        if res:
            # res is already a tuple (spdx, path)
            return res

    return None

def detect_main_license_scancode(data: dict) -> Optional[Tuple[str, str]] | str:
    """
    Identifies the main license of the project based on ScanCode results.

    Strategy:
    1. Search in most likely license candidates (e.g., LICENSE/license files).
    2. Use COPYING as fallback.
    3. Use other relevant paths as last resort.

    Returns: (spdx_expression, path) or "UNKNOWN" (simplified return type for this special case).
    """

    license_candidates = []
    copying_candidates = []
    other_candidates = []

    for entry in data.get("files", []):
        path = entry.get("path") or ""
        if not path:
            continue

        lower = path.lower()
        basename = os.path.basename(lower)

        # Ignore NOTICE/COPYRIGHT
        if basename.startswith("notice") or basename.startswith("copyright"):
            continue

        # Classification of candidates
        if basename.startswith("license"):
            license_candidates.append(entry)
        elif basename.startswith("copying"):
            copying_candidates.append(entry)
        # If not already a primary candidate and contains 'license' or 'copying'
        elif "license" in lower or "copying" in lower:
            other_candidates.append(entry)

    # 1. Try first choice: LICENSE file
    result = _pick_best_spdx(license_candidates)
    if result:
        return result

    # 2. Try fallback: COPYING file
    result = _pick_best_spdx(copying_candidates)
    if result:
        return result

    # 3. Try last resort: other relevant paths
    result = _pick_best_spdx(other_candidates)
    if result:
        return result

    return "UNKNOWN"


#  ------------ FUNCTIONS TO EXTRACT RESULTS FROM FILTERED LLM JSON -----------------

def extract_file_licenses_from_llm(llm_data: dict) -> Dict[str, str]:
    """
    Extracts the license for each file starting from the LLM-filtered JSON.
    llm_data has a different format than the original ScanCode JSON.
    """

    results = {}

    for f in llm_data.get("files", []):
        path = f.get("path")
        matches = f.get("matches", [])

        if not matches:
            continue

        # If there are multiple matches, combine them with AND (like ScanCode tool)
        unique_spdx = list({m.get("license_spdx") for m in matches if m.get("license_spdx")})

        if not unique_spdx:
            continue

        if len(unique_spdx) == 1:
            results[path] = unique_spdx[0]
        else:
            results[path] = " AND ".join(unique_spdx)

    return results
