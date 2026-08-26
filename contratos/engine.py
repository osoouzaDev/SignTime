"""API pública do núcleo, com leitura de planilha que libera o arquivo no Windows."""

from __future__ import annotations

from pathlib import Path

from . import engine_base as _base


def load_spreadsheet(
    path: Path, sheet_name: str | None = None
) -> _base.SpreadsheetData:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        try:
            frame = _base.pd.read_csv(path, sep=None, engine="python", dtype=object)
        except UnicodeDecodeError:
            frame = _base.pd.read_csv(
                path,
                sep=None,
                engine="python",
                dtype=object,
                encoding="latin1",
            )
        sheets = ["CSV"]
        selected = "CSV"
    elif suffix == ".xlsx":
        try:
            with _base.pd.ExcelFile(path) as book:
                sheets = [str(name) for name in book.sheet_names]
                if not sheets:
                    raise _base.ContractError("A planilha não possui abas.")
                selected = sheet_name if sheet_name in sheets else sheets[0]
                frame = _base.pd.read_excel(book, sheet_name=selected, dtype=object)
        except Exception as exc:
            if isinstance(exc, _base.ContractError):
                raise
            raise _base.ContractError(
                "Não foi possível abrir a planilha. Confirme se ela é um XLSX válido."
            ) from exc
    else:
        raise _base.ContractError("Use uma planilha no formato .xlsx ou .csv.")

    frame = frame.dropna(how="all")
    frame.columns = [_base.clean_value(column) for column in frame.columns]
    if not len(frame.columns):
        raise _base.ContractError("A planilha não possui cabeçalhos.")
    if frame.empty:
        raise _base.ContractError("A planilha não possui linhas preenchidas.")
    if len(frame) > _base.MAX_ROWS:
        raise _base.ContractError(
            f"A planilha possui mais de {_base.MAX_ROWS} linhas. Divida-a em lotes menores."
        )

    return _base.SpreadsheetData(
        frame=frame,
        sheets=sheets,
        selected_sheet=selected,
    )


# As funções do módulo-base consultam este nome em tempo de execução.
_base.load_spreadsheet = load_spreadsheet

ContractError = _base.ContractError
SpreadsheetData = _base.SpreadsheetData
analyze_inputs = _base.analyze_inputs
build_context = _base.build_context
clean_value = _base.clean_value
convert_docx_to_pdf = _base.convert_docx_to_pdf
format_cnpj = _base.format_cnpj
format_cpf = _base.format_cpf
generate_contracts_zip = _base.generate_contracts_zip
is_empty = _base.is_empty
normalize = _base.normalize
safe_filename = _base.safe_filename
suggest_mapping = _base.suggest_mapping
template_variables = _base.template_variables

__all__ = [
    "ContractError",
    "SpreadsheetData",
    "analyze_inputs",
    "build_context",
    "clean_value",
    "convert_docx_to_pdf",
    "format_cnpj",
    "format_cpf",
    "generate_contracts_zip",
    "is_empty",
    "load_spreadsheet",
    "normalize",
    "safe_filename",
    "suggest_mapping",
    "template_variables",
]
