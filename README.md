# SignTime

Uma interface local para gerar contratos em lote a partir de um modelo Word e de uma planilha Excel. O sistema identifica as variáveis do modelo, sugere a associação com as colunas da planilha, gera um arquivo por linha e devolve tudo em um ZIP com relatório.

## Como abrir

1. Dê dois cliques em `iniciar.bat`.
2. Aguarde o navegador abrir automaticamente.
3. Mantenha a janela preta aberta enquanto estiver usando o sistema.

Na primeira abertura, o sistema pode levar um pouco mais de tempo para preparar os componentes necessários.

## Como preparar o modelo Word

O arquivo precisa estar no formato `.docx`. Coloque as variáveis entre chaves duplas, por exemplo:

```text
CONTRATANTE: {{ nome_responsavel }}, inscrito no CPF {{ cpf }}.
EMPRESA: {{ nome_empresa }}, inscrita no CNPJ {{ cnpj }}.
DATA: {{ data }}.
```

As variáveis podem ter qualquer nome. A tela tentará associá-las automaticamente às colunas da planilha e permitirá corrigir cada associação.

## Como preparar a planilha

- Use `.xlsx` ou `.csv`.
- A primeira linha deve conter os nomes das colunas.
- Cada linha seguinte representa um contrato.
- CPF e CNPJ podem estar com ou sem pontuação; o sistema os formata.
- Células vazias são aceitas e viram texto vazio no contrato.

## Resultado

O ZIP contém os contratos em PDF, Word ou nos dois formatos, conforme a escolha feita na tela. Ele também inclui `relatorio_geracao.csv`, com o resultado de cada linha.

Para gerar PDF, o sistema usa o Microsoft Word instalado no computador. Se a conversão não estiver disponível, ele preserva o contrato em Word e registra o aviso no relatório.

## Clicksign

O envio para assinatura é opcional e permanece desligado por padrão. No executável, o token pode ser informado diretamente na tela e não fica armazenado. Se preferir deixá-lo configurado na máquina, mantenha ao lado do programa um arquivo `.env` com:

```text
CLICKSIGN_ACCESS_TOKEN=seu_token
```

Na tela, escolha o ambiente de teste ou produção e confirme os dados antes do envio. O histórico continua sendo registrado em `clicksign_envios.csv`.

## Limites e privacidade

- Até 25 MB por arquivo.
- Até 2.000 contratos por lote.
- O serviço abre apenas no próprio computador (`127.0.0.1`).
- Os arquivos temporários são apagados após a criação do ZIP.
