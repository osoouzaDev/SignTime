"""Integração isolada com a API v3 da Clicksign."""

from __future__ import annotations

import base64
import csv
import json
import threading
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ClicksignError(RuntimeError):
    """Erro legível de comunicação ou configuração da Clicksign."""


_CSV_LOCK = threading.Lock()


class ClicksignClient:
    def __init__(self, access_token: str, environment: str = "sandbox") -> None:
        token = (access_token or "").strip()
        if not token:
            raise ClicksignError("O token CLICKSIGN_ACCESS_TOKEN não foi configurado.")

        if environment not in {"sandbox", "production"}:
            raise ClicksignError("Ambiente Clicksign inválido.")

        self.access_token = token
        self.base_url = (
            "https://sandbox.clicksign.com/api/v3"
            if environment == "sandbox"
            else "https://app.clicksign.com/api/v3"
        )

    def _request(self, method: str, path: str, payload: dict) -> dict:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={
                "Authorization": self.access_token,
                "Content-Type": "application/vnd.api+json",
                "Accept": "application/vnd.api+json",
            },
        )

        try:
            with urlopen(request, timeout=60) as response:
                content = response.read().decode("utf-8", errors="replace").strip()
                return json.loads(content) if content else {}
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise ClicksignError(
                f"Clicksign respondeu com o código {exc.code}: {details[:500]}"
            ) from exc
        except URLError as exc:
            raise ClicksignError(f"Não foi possível acessar a Clicksign: {exc.reason}") from exc

    def send_contract(self, pdf_path: Path, name: str, email: str, title: str) -> dict:
        if not email or "@" not in email:
            raise ClicksignError(f"E-mail inválido para {name or 'o signatário'}.")
        if not name or "@" in name:
            raise ClicksignError("Nome do signatário ausente ou inválido.")

        envelope = self._request(
            "POST",
            "/envelopes",
            {
                "data": {
                    "type": "envelopes",
                    "attributes": {"name": title},
                }
            },
        )
        envelope_id = envelope["data"]["id"]

        encoded_pdf = base64.b64encode(pdf_path.read_bytes()).decode("ascii")
        document = self._request(
            "POST",
            f"/envelopes/{envelope_id}/documents",
            {
                "data": {
                    "type": "documents",
                    "attributes": {
                        "filename": pdf_path.name,
                        "content_base64": f"data:application/pdf;base64,{encoded_pdf}",
                        "metadata": {"origem": "gerador_visual_contratos"},
                    },
                }
            },
        )
        document_id = document["data"]["id"]

        signer = self._request(
            "POST",
            f"/envelopes/{envelope_id}/signers",
            {
                "data": {
                    "type": "signers",
                    "attributes": {"name": name, "email": email},
                }
            },
        )
        signer_id = signer["data"]["id"]

        relationships = {
            "document": {"data": {"type": "documents", "id": document_id}},
            "signer": {"data": {"type": "signers", "id": signer_id}},
        }
        self._request(
            "POST",
            f"/envelopes/{envelope_id}/requirements",
            {
                "data": {
                    "type": "requirements",
                    "attributes": {"action": "agree", "role": "sign"},
                    "relationships": relationships,
                }
            },
        )
        self._request(
            "POST",
            f"/envelopes/{envelope_id}/requirements",
            {
                "data": {
                    "type": "requirements",
                    "attributes": {
                        "action": "provide_evidence",
                        "auth": "handwritten",
                    },
                    "relationships": relationships,
                }
            },
        )
        self._request(
            "PATCH",
            f"/envelopes/{envelope_id}",
            {
                "data": {
                    "id": envelope_id,
                    "type": "envelopes",
                    "attributes": {"status": "running"},
                }
            },
        )
        self._request(
            "POST",
            f"/envelopes/{envelope_id}/notifications",
            {"data": {"type": "notifications", "attributes": {}}},
        )

        return {
            "envelope_id": envelope_id,
            "document_id": document_id,
            "signer_id": signer_id,
        }


def append_control_log(
    csv_path: Path,
    ids: dict,
    contract_type: str,
    name: str,
    company: str,
    email: str,
    filename: str,
) -> None:
    """Registra envios sem apagar o histórico já existente."""

    header = [
        "envelope_id",
        "document_id",
        "signer_id",
        "tipo",
        "nome_responsavel",
        "nome_empresa",
        "email",
        "arquivo_local",
    ]
    row = [
        ids.get("envelope_id", ""),
        ids.get("document_id", ""),
        ids.get("signer_id", ""),
        contract_type,
        name,
        company,
        email,
        filename,
    ]

    with _CSV_LOCK:
        new_file = not csv_path.exists()
        with csv_path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            if new_file:
                writer.writerow(header)
            writer.writerow(row)
