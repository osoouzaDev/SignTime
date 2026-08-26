"""Regras de análise, preenchimento e empacotamento dos contratos."""

from __future__ import annotations

import base64
import csv
import math
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from docxtpl import DocxTemplate

from .clicksign import ClicksignClient, ClicksignError, append_control_log


MAX_ROWS = 2_000


class ContractError(ValueError):
    """Erro de entrada apresentado diretamente na interface."""


@dataclass(frozen=True)
class SpreadsheetData:
    frame: pd.DataFrame
    sheets: list[str]
    selected_sheet: str


ALIASES: dict[str, tuple[str, ...]] = {
    "nome_responsavel": (
        "nome responsavel",
        "nome do responsavel",
        "seu nome completo",
        "nome completo",
        "contratante",
        "nome",
    ),
    "nome_empresa": (
        "razao social completa",
        "razao social",
        "nome da empresa",
        "empresa",
    ),
    "cpf": ("cpf", "cpf do responsavel", "documento cpf"),
    "cnpj": ("cnpj", "cnpj da empresa", "documento cnpj"),
    "email": ("email", "e mail", "correio eletronico"),
    "endereco": (
        "endereco comercial completo rua numero bairro cidade uf cep",
        "endereco comercial completo",
        "endereco completo",
        "endereco comercial",
        "endereco",
    ),
}


def is_empty(value: Any) -> bool:
    if value is None:
        return True
    try:
        if bool(pd.isna(value)):
            return True
    except (TypeError, ValueError):
        pass
    return str(value).strip() == ""


def clean_value(value: Any) -> str:
    if is_empty(value):
        return ""
    if isinstance(value, pd.Timestamp):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, (datetime, date)):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _digits(value: Any) -> str:
    return re.sub(r"\D", "", clean_value(value))


def format_cpf(value: Any) -> str:
    digits = _digits(value)
    if not digits:
        return ""
    digits = digits.zfill(11)
    if len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    return digits


def format_cnpj(value: Any) -> str:
    digits = _digits(value)
    if not digits:
        return ""
    digits = digits.zfill(14)
    if len(digits) == 14:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
    return digits


def normalize(text: Any) -> str:
    plain = unicodedata.normalize("NFKD", clean_value(text))
    plain = "".join(char for char in plain if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", plain.lower()).strip()


def safe_filename(value: Any, fallback: str = "Contrato") -> str:
    text = clean_value(value) or fallback
    text = re.sub(r'[\\/*?:"<>|]', "", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text[:100] or fallback


def load_spreadsheet(path: Path, sheet_name: str | None = None) -> SpreadsheetData:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        try:
            frame = pd.read_csv(path, sep=None, engine="python", dtype=object)
        except UnicodeDecodeError:
            frame = pd.read_csv(path, sep=None, engine="python", dtype=object, encoding="latin1")
        sheets = ["CSV"]
        selected = "CSV"
    elif suffix == ".xlsx":
        try:
            book = pd.ExcelFile(path)
        except Exception as exc:
            raise ContractError("Não foi possível abrir a planilha. Confirme se ela é um XLSX válido.") from exc
        sheets = [str(name) for name in book.sheet_names]
        if not sheets:
            raise ContractError("A planilha não possui abas.")
        selected = sheet_name if sheet_name in sheets else sheets[0]
        frame = pd.read_excel(path, sheet_name=selected, dtype=object)
    else:
        raise ContractError("Use uma planilha no formato .xlsx ou .csv.")

    frame = frame.dropna(how="all")
    frame.columns = [clean_value(column) for column in frame.columns]
    if not len(frame.columns):
        raise ContractError("A planilha não possui cabeçalhos.")
    if frame.empty:
        raise ContractError("A planilha não possui linhas preenchidas.")
    if len(frame) > MAX_ROWS:
        raise ContractError(f"A planilha possui mais de {MAX_ROWS} linhas. Divida-a em lotes menores.")

    return SpreadsheetData(frame=frame, sheets=sheets, selected_sheet=selected)


def template_variables(path: Path) -> list[str]:
    if path.suffix.lower() != ".docx":
        raise ContractError("O modelo precisa estar no formato .docx.")
    try:
        variables = DocxTemplate(str(path)).get_undeclared_template_variables()
    except (zipfile.BadZipFile, KeyError, OSError) as exc:
        raise ContractError("O arquivo enviado não é um modelo Word válido.") from exc
    except Exception as exc:
        raise ContractError(f"Não foi possível ler as variáveis do modelo: {exc}") from exc
    if not variables:
        raise ContractError("Nenhuma variável {{ assim }} foi encontrada no modelo Word.")
    return sorted(str(variable) for variable in variables)


def _find_column(columns: list[str], variable: str) -> tuple[str | None, str]:
    normalized_columns = {normalize(column): column for column in columns}
    variable_key = normalize(variable).replace(" ", "_")
    exact_key = normalize(variable)

    if exact_key in normalized_columns:
        return normalized_columns[exact_key], "high"

    aliases = ALIASES.get(variable_key, ())
    for alias in aliases:
        if alias in normalized_columns:
            return normalized_columns[alias], "high"

    compact_variable = exact_key.replace(" ", "")
    for normalized_column, original in normalized_columns.items():
        compact_column = normalized_column.replace(" ", "")
        if compact_variable and (
            compact_variable == compact_column
            or compact_variable in compact_column
            or compact_column in compact_variable
        ):
            return original, "medium"

    return None, "pending"


def _address_column(columns: list[str]) -> str | None:
    normalized_columns = {normalize(column): column for column in columns}
    for alias in ALIASES["endereco"]:
        if alias in normalized_columns:
            return normalized_columns[alias]
    for normalized_column, original in normalized_columns.items():
        if "endereco" in normalized_column:
            return original
    return None


def suggest_mapping(variables: list[str], columns: list[str]) -> tuple[dict, list[str]]:
    mapping: dict[str, dict[str, str]] = {}
    warnings: list[str] = []

    for variable in variables:
        key = normalize(variable).replace(" ", "_")
        if key in {"data", "data_atual", "hoje"}:
            mapping[variable] = {"kind": "system", "value": "today", "confidence": "high"}
            continue

        if key in {"texto_endereco", "endereco_formatado"}:
            column = _address_column(columns)
            if column:
                mapping[variable] = {
                    "kind": "address_clause",
                    "value": column,
                    "confidence": "high",
                }
            else:
                mapping[variable] = {"kind": "empty", "value": "", "confidence": "pending"}
                warnings.append(f"Escolha a coluna que preencherá {variable}.")
            continue

        column, confidence = _find_column(columns, variable)
        if column:
            mapping[variable] = {"kind": "column", "value": column, "confidence": confidence}
        else:
            mapping[variable] = {"kind": "empty", "value": "", "confidence": "pending"}
            warnings.append(f"Escolha a origem da variável {variable}.")

    return mapping, warnings


def analyze_inputs(template_path: Path, spreadsheet_path: Path, sheet_name: str | None = None) -> dict:
    variables = template_variables(template_path)
    spreadsheet = load_spreadsheet(spreadsheet_path, sheet_name)
    columns = list(spreadsheet.frame.columns)
    mapping, warnings = suggest_mapping(variables, columns)

    return {
        "variables": variables,
        "columns": columns,
        "rows": int(len(spreadsheet.frame)),
        "sheets": spreadsheet.sheets,
        "selected_sheet": spreadsheet.selected_sheet,
        "mapping": mapping,
        "warnings": warnings,
    }


def _context_value(variable: str, rule: dict, row: pd.Series) -> str:
    kind = rule.get("kind", "empty")
    value = rule.get("value", "")

    if kind == "system" and value == "today":
        result = datetime.now().strftime("%d/%m/%Y")
    elif kind == "constant":
        result = clean_value(value)
    elif kind in {"column", "address_clause"}:
        if value not in row.index:
            raise ContractError(f"A coluna '{value}' não existe mais na planilha.")
        result = clean_value(row.get(value))
        if kind == "address_clause":
            result = f"com endereço à {result}," if result else ""
    else:
        result = ""

    key = normalize(variable).replace(" ", "_")
    if key == "cpf":
        return format_cpf(result)
    if key == "cnpj":
        return format_cnpj(result)
    return result


def build_context(variables: list[str], mapping: dict, row: pd.Series) -> dict[str, str]:
    context = {
        variable: _context_value(variable, mapping.get(variable, {}), row)
        for variable in variables
    }
    if not context.get("nome_empresa") and context.get("nome_responsavel"):
        context["nome_empresa"] = context["nome_responsavel"]
    return context


def _unique_name(base: str, used_names: set[str]) -> str:
    candidate = base
    number = 2
    while candidate.lower() in used_names:
        candidate = f"{base}_{number}"
        number += 1
    used_names.add(candidate.lower())
    return candidate


def _convert_with_word(docx_path: Path, pdf_path: Path) -> None:
    def ps_literal(path: Path) -> str:
        return str(path.resolve()).replace("'", "''")

    script = f"""
$ErrorActionPreference = 'Stop'
$word = $null
$document = $null
try {{
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $document = $word.Documents.Open('{ps_literal(docx_path)}')
    $document.ExportAsFixedFormat('{ps_literal(pdf_path)}', 17)
}} finally {{
    if ($null -ne $document) {{ $document.Close(0) }}
    if ($null -ne $word) {{ $word.Quit() }}
    if ($null -ne $document) {{ [void][Runtime.InteropServices.Marshal]::ReleaseComObject($document) }}
    if ($null -ne $word) {{ [void][Runtime.InteropServices.Marshal]::ReleaseComObject($word) }}
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}}
"""
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
        capture_output=True,
        text=True,
        timeout=120,
        creationflags=creation_flags,
        check=False,
    )
    if result.returncode != 0 or not pdf_path.exists():
        details = (result.stderr or result.stdout or "Falha desconhecida do Word").strip()
        raise RuntimeError(details[-700:])


def _convert_with_libreoffice(docx_path: Path, pdf_path: Path) -> None:
    executable = shutil.which("soffice") or shutil.which("libreoffice")
    if not executable:
        raise RuntimeError("LibreOffice não encontrado.")
    result = subprocess.run(
        [
            executable,
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(pdf_path.parent),
            str(docx_path),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    generated = pdf_path.parent / f"{docx_path.stem}.pdf"
    if result.returncode != 0 or not generated.exists():
        raise RuntimeError((result.stderr or result.stdout or "Falha no LibreOffice").strip())
    if generated != pdf_path:
        generated.replace(pdf_path)


def convert_docx_to_pdf(docx_path: Path, pdf_path: Path) -> None:
    """Usa Word no Windows e LibreOffice nos demais ambientes."""

    if os.name == "nt":
        try:
            _convert_with_word(docx_path, pdf_path)
            return
        except Exception as word_error:
            try:
                _convert_with_libreoffice(docx_path, pdf_path)
                return
            except Exception:
                raise RuntimeError(
                    "Não foi possível converter pelo Microsoft Word. "
                    f"Detalhe: {word_error}"
                ) from word_error
    _convert_with_libreoffice(docx_path, pdf_path)


def _known_value(row: pd.Series, alias_key: str) -> str:
    columns = list(row.index)
    column, _ = _find_column(columns, alias_key)
    if alias_key == "endereco" and not column:
        column = _address_column(columns)
    return clean_value(row.get(column)) if column else ""


def _validate_mapping(variables: list[str], mapping: dict, columns: list[str]) -> None:
    for variable in variables:
        rule = mapping.get(variable, {})
        kind = rule.get("kind")
        value = rule.get("value", "")
        if kind not in {"system", "constant", "column", "address_clause"}:
            raise ContractError(f"Defina a origem da variável '{variable}'.")
        if kind in {"column", "address_clause"} and value not in columns:
            raise ContractError(f"A coluna escolhida para '{variable}' não existe na planilha.")


def generate_contracts_zip(
    template_path: Path,
    spreadsheet_path: Path,
    mapping: dict,
    zip_path: Path,
    *,
    sheet_name: str | None = None,
    output_format: str = "pdf",
    filename_variable: str = "nome_responsavel",
    clicksign: dict | None = None,
    clicksign_log_path: Path | None = None,
    converter: Callable[[Path, Path], None] = convert_docx_to_pdf,
) -> dict:
    if output_format not in {"pdf", "docx", "both"}:
        raise ContractError("Formato de saída inválido.")

    variables = template_variables(template_path)
    spreadsheet = load_spreadsheet(spreadsheet_path, sheet_name)
    columns = list(spreadsheet.frame.columns)
    _validate_mapping(variables, mapping, columns)

    clicksign_enabled = bool(clicksign and clicksign.get("enabled"))
    clicksign_client: ClicksignClient | None = None
    if clicksign_enabled:
        if not clicksign.get("confirmed"):
            raise ContractError("Confirme o envio antes de usar a Clicksign.")
        clicksign_client = ClicksignClient(
            clicksign.get("access_token", ""),
            clicksign.get("environment", "sandbox"),
        )

    used_names: set[str] = set()
    report: list[dict[str, str]] = []
    files_for_zip: list[Path] = []
    pdf_fallbacks = 0
    generated = 0
    errors = 0
    sent = 0

    with tempfile.TemporaryDirectory(prefix="contratos-gerados-") as temp_name:
        work_dir = Path(temp_name)

        for position, (_, row) in enumerate(spreadsheet.frame.iterrows(), start=2):
            filename = ""
            status = "gerado"
            details = ""
            clicksign_status = "não solicitado"
            envelope_id = ""

            try:
                context = build_context(variables, mapping, row)
                name_value = context.get(filename_variable, "")
                if not name_value:
                    name_value = (
                        context.get("nome_responsavel")
                        or context.get("nome_empresa")
                        or _known_value(row, "nome_responsavel")
                        or f"Linha {position}"
                    )
                contract_type = "CNPJ" if "cnpj" in context else "CPF" if "cpf" in context else "Contrato"
                base = safe_filename(f"{name_value}_{contract_type}")
                filename = _unique_name(base, used_names)

                docx_path = work_dir / f"{filename}.docx"
                pdf_path = work_dir / f"{filename}.pdf"

                document = DocxTemplate(str(template_path))
                document.render(context)
                document.save(str(docx_path))

                if output_format in {"pdf", "both"}:
                    try:
                        converter(docx_path, pdf_path)
                        files_for_zip.append(pdf_path)
                    except Exception as exc:
                        pdf_fallbacks += 1
                        status = "gerado com aviso"
                        details = f"PDF indisponível; DOCX incluído. {str(exc)[:450]}"
                        if docx_path not in files_for_zip:
                            files_for_zip.append(docx_path)

                if output_format in {"docx", "both"} and docx_path not in files_for_zip:
                    files_for_zip.append(docx_path)

                generated += 1

                if clicksign_client:
                    if not pdf_path.exists():
                        clicksign_status = "não enviado: PDF indisponível"
                    else:
                        signer_name = context.get("nome_responsavel") or _known_value(row, "nome_responsavel")
                        company = context.get("nome_empresa") or _known_value(row, "nome_empresa")
                        email = context.get("email") or _known_value(row, "email")
                        title = f"Contrato - {company or signer_name}"
                        try:
                            ids = clicksign_client.send_contract(
                                pdf_path, signer_name, email, title
                            )
                            clicksign_status = "enviado"
                            envelope_id = ids["envelope_id"]
                            sent += 1
                            if clicksign_log_path:
                                append_control_log(
                                    clicksign_log_path,
                                    ids,
                                    contract_type,
                                    signer_name,
                                    company,
                                    email,
                                    pdf_path.name,
                                )
                        except ClicksignError as exc:
                            clicksign_status = f"erro: {str(exc)[:350]}"
            except Exception as exc:
                status = "erro"
                details = str(exc)[:500]
                clicksign_status = "não enviado"
                errors += 1

            report.append(
                {
                    "linha_planilha": str(position),
                    "arquivo": filename,
                    "status": status,
                    "detalhe": details,
                    "clicksign": clicksign_status,
                    "envelope_id": envelope_id,
                }
            )

        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path in files_for_zip:
                if file_path.exists():
                    archive.write(file_path, arcname=file_path.name)

            report_buffer = tempfile.SpooledTemporaryFile(mode="w+", newline="", encoding="utf-8")
            writer = csv.DictWriter(
                report_buffer,
                fieldnames=[
                    "linha_planilha",
                    "arquivo",
                    "status",
                    "detalhe",
                    "clicksign",
                    "envelope_id",
                ],
            )
            writer.writeheader()
            writer.writerows(report)
            report_buffer.seek(0)
            archive.writestr("relatorio_geracao.csv", "\ufeff" + report_buffer.read())
            report_buffer.close()

    return {
        "generated": generated,
        "errors": errors,
        "pdf_fallbacks": pdf_fallbacks,
        "sent": sent,
        "rows": int(len(spreadsheet.frame)),
        "filename": zip_path.name,
    }
