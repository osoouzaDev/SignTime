from docxtpl import DocxTemplate
import pandas as pd
from pathlib import Path
from datetime import datetime
import re
import math
from docx2pdf import convert

BASE_DIR = Path(__file__).parent

PASTA_DOCS = BASE_DIR / "documentosCNPJ"
ARQUIVO_XLSX = PASTA_DOCS / "planilha_mentoria_cnpj.xlsx"
ARQUIVO_TEMPLATE = PASTA_DOCS / "contrato_mentoria_cnpj.docx"

PASTA_SAIDA = BASE_DIR / "contratosProntos"

def vazio(valor):
    return valor is None or (isinstance(valor, float) and math.isnan(valor)) or str(valor).strip() == ""

def limpar(valor):
    return "" if vazio(valor) else str(valor).strip()

def formatar_cnpj(valor):
    texto = re.sub(r"\D", "", str(valor)).zfill(14)
    if len(texto) == 14:
        return f"{texto[:2]}.{texto[2:5]}.{texto[5:8]}/{texto[8:12]}-{texto[12:]}"
    return texto

def formatar_cpf(valor):
    texto = re.sub(r"\D", "", str(valor)).zfill(11)
    if len(texto) == 11:
        return f"{texto[:3]}.{texto[3:6]}.{texto[6:9]}-{texto[9:]}"
    return texto

def montar_texto_endereco(endereco):
    endereco = limpar(endereco)
    return f"com endereço à {endereco}," if endereco else ""

def nome_seguro(nome):
    return re.sub(r'[\\/*?:"<>|]', "", nome)

def main():
    if not ARQUIVO_XLSX.exists():
        raise FileNotFoundError(f"Planilha não encontrada: {ARQUIVO_XLSX}")

    if not ARQUIVO_TEMPLATE.exists():
        raise FileNotFoundError(f"Template não encontrado: {ARQUIVO_TEMPLATE}")

    PASTA_SAIDA.mkdir(exist_ok=True)

    df = pd.read_excel(ARQUIVO_XLSX).dropna(how="all")

    data = datetime.now().strftime("%d/%m/%Y")

    for _, row in df.iterrows():
        doc = DocxTemplate(str(ARQUIVO_TEMPLATE))

        contexto = {
            "nome_empresa": limpar(row.get("Razão Social Completa")),
            "cnpj": formatar_cnpj(row.get("CNPJ")),
            "nome_responsavel": limpar(row.get("Seu nome completo:")),
            "cpf": formatar_cpf(row.get("CPF")),
            "texto_endereco": montar_texto_endereco(row.get("Endereço Comercial Completo (Rua, Número, Bairro, Cidade/UF, CEP)")),
            "data": data
        }

        doc.render(contexto)

        nome = nome_seguro(f"{contexto['nome_responsavel']}_{contexto['cpf']}")

        caminho_docx = PASTA_SAIDA / f"{nome}_CNPJ.docx"

        caminho_pdf = PASTA_SAIDA / f"{nome}_CNPJ.pdf"

        doc.save(str(caminho_docx))

        try:
            convert(str(caminho_docx), str(caminho_pdf))

            caminho_docx.unlink()

        except Exception as e:
            print(f"Erro ao converter {nome}: {e}")

    print("Contratos CNPJ gerados em PDF com sucesso!")

if __name__ == "__main__":
    main()