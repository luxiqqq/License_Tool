# Questo file contiene la TUA logica di business pura, senza FastAPI
from app.models.schemas import AnalyzeResponse, LicenseIssue
from app.services.github_client import clone_repo
from app.services.scancode_service import (
    run_scancode,
    detect_main_license_scancode,
    extract_file_licenses_from_llm, filter_with_llm,
)
from app.services.compatibility import check_compatibility
from app.services.llm_helper import enrich_with_llm_suggestions
from app.services.report_service import generate_report

def run_analysis_logic(owner: str, repo: str, oauth_token: str) -> AnalyzeResponse:
    """
    Esegue l'intera pipeline: Clone -> Scan -> LLM -> Report
    """
    # 1) Clona il repo (con token dinamico)
    clone_result = clone_repo(owner, repo, oauth_token)
    if not clone_result.success:
        raise ValueError(f"Errore clonazione: {clone_result.error}")

    repo_path = clone_result.repo_path

    # 2) Esegui ScanCode
    scan_raw = run_scancode(repo_path)

    # 3) Main License
    main_license = detect_main_license_scancode(scan_raw)

    # 4) Filtro LLM
    llm_clean = filter_with_llm(scan_raw)
    file_licenses = extract_file_licenses_from_llm(llm_clean)

    # 5) Compatibilità
    compatibility = check_compatibility(main_license, file_licenses)

    # 6) Suggerimenti AI
    enriched_issues = enrich_with_llm_suggestions(compatibility["issues"])

    # 7) Mapping Pydantic
    license_issue_models = [
        LicenseIssue(
            file_path=i["file_path"],
            detected_license=i["detected_license"],
            compatible=i["compatible"],
            reason=i.get("reason"),
            suggestion=i.get("suggestion"),
            regenerated_code_path=i.get("regenerated_code_path"),
        )
        for i in enriched_issues
    ]

    # 8) Genera report su disco
    report_path = generate_report(repo_path, main_license, license_issue_models)

    return AnalyzeResponse(
        repository=f"{owner}/{repo}",
        main_license=main_license,
        issues=license_issue_models,
        report_path=report_path,
    )