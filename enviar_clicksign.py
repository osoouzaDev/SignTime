import base64
import csv
import os
import re
from pathlib import Path

from dotenv import load_dotenv
import pandas as pd
import requests

load_dotenv()

BASE_DIR = Path(__file__).parent

PASTA_CONTRATOS = BASE_DIR / "contratosProntos"
ARQUIVO_XLSX_CNPJ = BASE_DIR / "documentosCNPJ" / "planilha_mentoria_cnpj.xlsx"
ARQUIVO_XLSX_CPF = BASE_DIR / "documentosCPF" / "planilha_mentoria_cpf.xlsx"
ARQUIVO_CONTROLE = BASE_DIR / "clicksign_envios.csv"

BASE_URL = "https://sandbox.clicksign.com/api/v3" # Teste
# BASE_URL = "https://app.clicksign.com/api/v3"  # Produção

ACCESS_TOKEN = os.getenv("CLICKSIGN_ACCESS_TOKEN", "").strip()
CONTINUAR_EM_CASO_DE_ERRO = True


def vazio(valor) -> bool:
    if valor is None:
        return True
    txt = str(valor).strip()
    return txt == "" or txt.lower() == "nan"


def limpar(valor) -> str:
    return "" if vazio(valor) else str(valor).strip()


def nome_seguro(nome: str) -> str:
    nome = limpar(nome)
    return re.sub(r'[\\/*?:"<>|]', "", nome).strip()


def pdf_para_base64(caminho_pdf: Path) -> str:
    conteudo = base64.b64encode(caminho_pdf.read_bytes()).decode("utf-8")
    return f"data:application/pdf;base64,{conteudo}"


def headers_jsonapi() -> dict:
    if not ACCESS_TOKEN:
        raise ValueError("A variável de ambiente CLICKSIGN_ACCESS_TOKEN não foi definida.")

    return {
        "Authorization": ACCESS_TOKEN,
        "Content-Type": "application/vnd.api+json",
        "Accept": "application/vnd.api+json",
    }


def post_jsonapi(url: str, payload: dict) -> dict:
    resp = requests.post(url, headers=headers_jsonapi(), json=payload, timeout=60)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"POST {url} -> {resp.status_code}: {resp.text}")
    return resp.json()


def patch_jsonapi(url: str, payload: dict) -> dict:
    resp = requests.patch(url, headers=headers_jsonapi(), json=payload, timeout=60)
    if resp.status_code not in (200, 204):
        raise RuntimeError(f"PATCH {url} -> {resp.status_code}: {resp.text}")
    return {} if not resp.text.strip() else resp.json()


def ler_planilha(caminho_xlsx: Path, tipo: str) -> list[dict]:
    if not caminho_xlsx.exists():
        raise FileNotFoundError(f"Planilha não encontrada: {caminho_xlsx}")

    df = pd.read_excel(caminho_xlsx).dropna(how="all")
    registros = []

    for _, row in df.iterrows():
        nome_responsavel = limpar(row.get("Seu nome completo:"))
        email = limpar(row.get("EMAIL"))
        nome_empresa = limpar(row.get("Razão Social Completa"))

        if not nome_responsavel:
            continue

        if "@" in nome_responsavel:
            raise ValueError(
                f"O campo 'Seu nome completo:' está preenchido com e-mail: {nome_responsavel}"
            )

        registros.append({
            "tipo": tipo,
            "nome_responsavel": nome_responsavel,
            "nome_empresa": nome_empresa,
            "email": email,
        })

    return registros


def localizar_pdf(nome_responsavel: str, tipo: str) -> Path | None:
    nome_base = nome_seguro(nome_responsavel).lower()

    for arquivo in PASTA_CONTRATOS.glob("*.pdf"):
        nome_arquivo = arquivo.stem.lower()
        if nome_base in nome_arquivo and tipo.lower() in nome_arquivo:
            return arquivo

    return None


def garantir_csv():
    if not ARQUIVO_CONTROLE.exists():
        with open(ARQUIVO_CONTROLE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "envelope_id",
                "document_id",
                "signer_id",
                "tipo",
                "nome_responsavel",
                "nome_empresa",
                "email",
                "arquivo_local",
            ])


def registrar_envio(
    envelope_id: str,
    document_id: str,
    signer_id: str,
    cliente: dict,
    arquivo: Path,
):
    garantir_csv()

    with open(ARQUIVO_CONTROLE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            envelope_id,
            document_id,
            signer_id,
            cliente["tipo"],
            cliente["nome_responsavel"],
            cliente["nome_empresa"],
            cliente["email"],
            str(arquivo),
        ])


def criar_envelope(nome_envelope: str) -> str:
    payload = {
        "data": {
            "type": "envelopes",
            "attributes": {
                "name": nome_envelope
            }
        }
    }

    data = post_jsonapi(f"{BASE_URL}/envelopes", payload)
    return data["data"]["id"]


def adicionar_documento(envelope_id: str, caminho_pdf: Path) -> str:
    payload = {
        "data": {
            "type": "documents",
            "attributes": {
                "filename": caminho_pdf.name,
                "content_base64": pdf_para_base64(caminho_pdf),
                "metadata": {
                    "origem": "automacao_python"
                }
            }
        }
    }

    data = post_jsonapi(f"{BASE_URL}/envelopes/{envelope_id}/documents", payload)
    return data["data"]["id"]


def adicionar_signatario(envelope_id: str, nome: str, email: str) -> str:
    nome = limpar(nome)
    email = limpar(email)

    if not nome:
        raise ValueError(f"Nome do signatário não informado para o e-mail {email}")

    if "@" in nome:
        raise ValueError(f"O nome do signatário está com aparência de e-mail: {nome}")

    if not email:
        raise ValueError(f"E-mail do signatário não informado para {nome}")

    payload = {
        "data": {
            "type": "signers",
            "attributes": {
                "name": nome,
                "email": email
            }
        }
    }

    data = post_jsonapi(f"{BASE_URL}/envelopes/{envelope_id}/signers", payload)
    return data["data"]["id"]


def criar_requisito_qualificacao(envelope_id: str, document_id: str, signer_id: str):
    payload = {
        "data": {
            "type": "requirements",
            "attributes": {
                "action": "agree",
                "role": "sign"
            },
            "relationships": {
                "document": {
                    "data": {"type": "documents", "id": document_id}
                },
                "signer": {
                    "data": {"type": "signers", "id": signer_id}
                }
            }
        }
    }

    post_jsonapi(f"{BASE_URL}/envelopes/{envelope_id}/requirements", payload)


def criar_requisito_autenticacao_manuscrita(envelope_id: str, document_id: str, signer_id: str):
    payload = {
        "data": {
            "type": "requirements",
            "attributes": {
                "action": "provide_evidence",
                "auth": "handwritten"
            },
            "relationships": {
                "document": {
                    "data": {"type": "documents", "id": document_id}
                },
                "signer": {
                    "data": {"type": "signers", "id": signer_id}
                }
            }
        }
    }

    post_jsonapi(f"{BASE_URL}/envelopes/{envelope_id}/requirements", payload)


def ativar_envelope(envelope_id: str):
    payload = {
        "data": {
            "id": envelope_id,
            "type": "envelopes",
            "attributes": {
                "status": "running"
            }
        }
    }

    patch_jsonapi(f"{BASE_URL}/envelopes/{envelope_id}", payload)


def notificar_signatarios(envelope_id: str):
    payload = {
        "data": {
            "type": "notifications",
            "attributes": {}
        }
    }

    post_jsonapi(f"{BASE_URL}/envelopes/{envelope_id}/notifications", payload)


def enviar_cliente(cliente: dict):
    nome = cliente["nome_responsavel"]
    email = cliente["email"]
    tipo = cliente["tipo"]
    empresa = cliente["nome_empresa"]

    if not email:
        raise ValueError(f"Cliente sem email: {nome} ({tipo})")

    pdf = localizar_pdf(nome, tipo)
    if not pdf:
        raise FileNotFoundError(f"PDF não encontrado para {nome} ({tipo})")

    titulo = f"Contrato de Mentoria - {empresa or nome}"

    envelope_id = criar_envelope(titulo)
    document_id = adicionar_documento(envelope_id, pdf)
    signer_id = adicionar_signatario(envelope_id, nome, email)

    criar_requisito_qualificacao(envelope_id, document_id, signer_id)
    criar_requisito_autenticacao_manuscrita(envelope_id, document_id, signer_id)

    ativar_envelope(envelope_id)
    notificar_signatarios(envelope_id)

    registrar_envio(envelope_id, document_id, signer_id, cliente, pdf)

    print(f"[OK] {nome} ({tipo}) -> {email}")
    print(f"     envelope_id: {envelope_id}")
    print(f"     document_id: {document_id}")
    print(f"     signer_id:   {signer_id}")
    print("-" * 60)


def main():
    if not PASTA_CONTRATOS.exists():
        raise FileNotFoundError(f"Pasta não encontrada: {PASTA_CONTRATOS}")

    clientes = []
    clientes += ler_planilha(ARQUIVO_XLSX_CNPJ, "CNPJ")
    clientes += ler_planilha(ARQUIVO_XLSX_CPF, "CPF")

    enviados = 0
    erros = []

    for cliente in clientes:
        try:
            enviar_cliente(cliente)
            enviados += 1
        except Exception as e:
            msg = f"{cliente['nome_responsavel']} ({cliente['tipo']}): {e}"
            if CONTINUAR_EM_CASO_DE_ERRO:
                erros.append(msg)
                print(f"[ERRO] {msg}")
            else:
                raise

    print("\n===== RESUMO =====")
    print(f"Enviados: {enviados}")

    if erros:
        print("\nErros:")
        for erro in erros:
            print("-", erro)


if __name__ == "__main__":
    main()