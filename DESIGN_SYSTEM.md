# Facilita Contratos — Design System

> Fonte de verdade visual da interface web, extraída da implementação atual em `web/styles.css` e `web/index.html`.
>
> **Versão:** 1.0  
> **Atualizado em:** 25 de agosto de 2026  
> **Idioma da interface:** Português do Brasil (`pt-BR`)

## 1. Essência da marca

O Facilita Contratos combina a seriedade esperada de uma ferramenta jurídica com uma experiência simples e acolhedora. A interface deve transmitir:

- **Confiança:** cores profundas, contraste alto e mensagens objetivas.
- **Clareza:** uma tarefa principal por vez, hierarquia evidente e instruções curtas.
- **Segurança:** privacidade e execução local aparecem como parte da experiência, não como detalhe técnico.
- **Eficiência:** o fluxo é linear — arquivos, conferência e resultado.
- **Calma:** superfícies quentes, bordas suaves e movimento discreto.

### Personalidade visual

**Editorial, sóbria, humana e precisa.** O verde-floresta estabelece confiança; o fundo marfim evita a frieza do branco puro; a terracota cria ênfase sem parecer alarmante; a tipografia serifada adiciona caráter nos títulos principais.

## 2. Identidade

### Assinatura

- **Nome:** Facilita Contratos
- **Monograma:** `FC`
- **Marca gráfica atual:** bloco verde-floresta de `42 × 42 px`, raio de `13 px`, monograma branco centralizado.
- **Construção do nome:** “Facilita” em destaque e “Contratos” como complemento.
- **Mensagem de confiança:** “Execução local e segura”, acompanhada de indicador verde.

### Uso recomendado

- Preserve uma área livre mínima de `12 px` ao redor do monograma.
- Use o monograma sobre superfícies claras.
- Não altere a proporção, não aplique contorno e não substitua o verde principal por uma cor de estado.
- Em telas estreitas, o complemento “Contratos” e o selo de privacidade podem ser ocultados; “Facilita” e o monograma permanecem.

## 3. Cores

### Tokens principais

| Token CSS | Valor | Função |
|---|---:|---|
| `--ink` | `#17221F` | Texto principal, títulos e marca nominativa |
| `--ink-soft` | `#53605C` | Texto secundário, descrições e ajuda |
| `--forest` | `#153F36` | Cor de marca, ação primária e estados ativos |
| `--forest-dark` | `#0D2D27` | Hover da ação primária |
| `--sage` | `#DCE9DF` | Fundo suave para código e destaques neutros |
| `--sage-strong` | `#79A68F` | Bordas ativas, detalhes e realces |
| `--paper` | `#FFFEFA` | Superfície principal dos cartões |
| `--canvas` | `#F3F1E9` | Fundo geral da aplicação |
| `--line` | `#DEDDD5` | Divisores e bordas sutis |
| `--line-dark` | `#C9CBC3` | Bordas de campos e controles |
| `--accent` | `#E56D4D` | Foco e ênfase da marca |
| `--accent-dark` | `#C65237` | Kicker, numeração de etapa e microdestaques |
| `--success` | `#27735C` | Conclusão e retorno positivo |
| `--warning` | `#A36520` | Avisos |
| `--danger` | `#B7443E` | Erros e associações pendentes |

### Cores auxiliares implementadas

| Uso | Valor |
|---|---:|
| Ícone de arquivo Word | `#2C5793` |
| Ícone de planilha | `#28734F` |
| Associação automática/alta confiança | `#5F9B7E` |
| Associação de média confiança | `#D49749` |
| Toast de erro | `#522C29` |
| Superfície neutra de controles | `#F4F4EF` |
| Superfície de cabeçalho interno | `#F7F7F2` |
| Superfície de upload | `#FBFBF7` |
| Superfície de upload válido | `#F4FAF6` |
| Superfície de processamento | `#F0F6F1` |

### Regras de aplicação

- Use `--forest` para a ação primária, nunca `--accent`.
- Reserve terracota para orientação e foco; ela não representa erro.
- Use as cores de estado junto de texto ou ícone. Cor isolada não deve carregar significado.
- Prefira `--paper` a branco puro em grandes superfícies.
- Fundos auxiliares devem ser usados dentro de `--paper`, mantendo a hierarquia entre tela, cartão e controle.

### Contraste de referência

| Combinação | Razão aproximada | Resultado |
|---|---:|---|
| `--ink` sobre `--paper` | `16.19:1` | AAA |
| `--ink-soft` sobre `--paper` | `6.51:1` | AA/AAA para texto grande |
| `--forest` sobre `--paper` | `11.59:1` | AAA |
| Branco sobre `--forest` | `11.69:1` | AAA |
| Branco sobre toast `#522C29` | `11.99:1` | AAA |
| `--accent-dark` sobre `--paper` | `4.46:1` | Limítrofe para texto pequeno |

> **Atenção:** textos pequenos em `#828985` e etapas inativas em `#89908D` têm contraste abaixo de AA. Ao evoluir o sistema, escureça essas cores ou aumente tamanho/peso sem alterar a hierarquia visual.

## 4. Tipografia

### Famílias

| Papel | Família | Fallback |
|---|---|---|
| Interface e conteúdo | `Segoe UI` | `Arial, sans-serif` |
| Títulos editoriais | `Georgia` | `Times New Roman, serif` |
| Variáveis e código | `Consolas` | `monospace` |

### Escala implementada

| Estilo | Tamanho | Peso | Entrelinha | Uso |
|---|---:|---:|---:|---|
| Display | `clamp(41px, 4.1vw, 58px)` | `500` | `1.02` | Título principal da página |
| Display mobile | `39px` | `500` | `1.02` | Título principal abaixo de `680px` |
| Título de cartão | `clamp(25px, 3vw, 32px)` | padrão forte | `1.2` | Título da tarefa |
| Título de resultado | `31px` | `500` | padrão | Confirmação final |
| Título de seção | `17px` | padrão forte | padrão | Etapas internas |
| Marca | `18px` | forte | padrão | Nome “Facilita” |
| Corpo | `15px` | `400` | `1.5` | Conteúdo geral |
| Descrição longa | `15px` | `400` | `1.7` | Apresentação do fluxo |
| Texto auxiliar | `13px` | `400–750` | padrão | Instruções e nomes de arquivo |
| Rótulo | `11px` | `750–800` | padrão | Campos, ações compactas e metadados |
| Kicker | `11px` | `800` | padrão | Seção em caixa alta, tracking `0.16em` |
| Microtexto | `10px` | `400` | padrão | Notas e detalhes operacionais |
| Código/variável | `11px` | `700` | padrão | `{{ nome_variavel }}` |

### Regras tipográficas

- Use Georgia apenas em mensagens de alto valor: abertura e conclusão.
- Use caixa alta somente em kickers curtos.
- Títulos editoriais usam tracking negativo entre `-0.03em` e `-0.045em`.
- Textos operacionais devem permanecer em Segoe UI para leitura rápida.
- Variáveis de contrato sempre usam Consolas e chaves duplas: `{{ nome_cliente }}`.
- Não use corpo de texto abaixo de `11 px`; microtextos de `10 px` devem ser revistos quando forem essenciais.

## 5. Espaçamento e dimensões

O CSS atual não declara tokens de espaçamento. A escala abaixo consolida os valores recorrentes da interface.

| Nível | Valor | Uso típico |
|---|---:|---|
| `space-1` | `3px` | Ajustes internos mínimos |
| `space-2` | `6px` | Pares de texto e pequenos elementos |
| `space-3` | `8px` | Ícone com rótulo |
| `space-4` | `10px` | Grupo compacto de ações |
| `space-5` | `12px` | Respiro entre elementos relacionados |
| `space-6` | `14px` | Grid de uploads e células |
| `space-7` | `16px` | Conteúdo de componentes compactos |
| `space-8` | `18px` | Painéis e campos |
| `space-9` | `20px` | Blocos internos |
| `space-10` | `24px` | Separação de seções pequenas |
| `space-11` | `34px` | Separação de etapas |
| `space-12` | `46px` | Padding máximo do cartão principal |

### Alvos e controles

- Campo padrão: altura mínima de `43 px`.
- Botão principal/secundário: altura mínima de `50 px`.
- Controle segmentado: `43 px`, com opções internas de `35 px`.
- Switch: `42 × 24 px`; indicador interno de `18 px`.
- Dropzone: mínimo de `148 px` no desktop e `122 px` no mobile.

## 6. Formas, bordas e elevação

### Raios

| Valor | Aplicação |
|---:|---|
| `4–6px` | Código e seleção interna |
| `9–10px` | Campos, botões e ícones de arquivo |
| `12–14px` | Painéis, toast e cartões internos |
| `16px` | Dropzones |
| `18px` | Cartão principal no mobile |
| `24px` | Cartão principal no desktop |
| `999px` | Selos, indicadores e switch |
| `50%` | Etapas, ícone de sucesso e pontos de estado |

### Bordas

- Padrão sutil: `1px solid var(--line)`.
- Campo interativo: `1px solid var(--line-dark)`.
- Upload vazio: borda tracejada.
- Upload válido: borda sólida `#9FBFAD`.
- Foco do navegador: `--accent`, com offset de `3 px`.

### Sombras

| Papel | Valor |
|---|---|
| Cartão principal | `0 18px 50px rgba(31, 42, 37, 0.09)` |
| Marca | `0 7px 20px rgba(21, 63, 54, 0.20)` |
| Botão primário | `0 9px 22px rgba(21, 63, 54, 0.17)` |
| Seleção segmentada | `0 2px 8px rgba(32, 43, 38, 0.08)` |
| Toast | `0 15px 35px rgba(45, 27, 25, 0.22)` |

Sombras indicam elevação, nunca decoração gratuita. Use apenas um nível dominante por região.

## 7. Layout

### Estrutura desktop

- Largura máxima da página: `1240 px`.
- Margem lateral: `24 px` (`48 px` descontados da largura total).
- Topbar: `92 px` de altura.
- Área principal: duas colunas.
  - Coluna editorial: entre `270` e `330 px`.
  - Coluna de tarefa: até `820 px`.
- Espaço entre colunas: `clamp(44px, 6vw, 90px)`.
- Cartão principal: altura mínima de `560 px`; padding responsivo de `26` a `46 px`.
- A coluna editorial permanece fixa durante a rolagem (`sticky`, topo de `32 px`).

### Fundo

O canvas usa `--canvas` com um halo radial verde-sálvia no canto superior esquerdo. O efeito deve permanecer discreto e não competir com o conteúdo.

### Responsividade

#### Até `940 px`

- O layout passa para uma coluna.
- A apresentação deixa de ser fixa.
- A jornada se torna horizontal em três colunas.
- Textos das etapas são ocultados; os indicadores numéricos permanecem.
- O cartão de dica é ocultado.

#### Até `680 px`

- Margem lateral passa a `14 px`.
- Topbar passa a `76 px`.
- Complemento da marca e selo de privacidade são ocultados.
- Uploads, opções e configuração da Clicksign passam para uma coluna.
- Cartão principal usa padding `24px 18px` e raio `18 px`.
- Mapeamentos passam a uma coluna e a seta é ocultada.
- Ações do resultado ocupam a largura total e ficam empilhadas.
- Rótulos do resumo são ocultados, preservando os números.

## 8. Componentes

### 8.1 Marca

**Anatomia:** monograma, nome principal e complemento.  
**Comportamento:** o link leva ao início e possui nome acessível completo.  
**Seletor:** `.brand`, `.brand-mark`.

### 8.2 Selo de privacidade

**Anatomia:** ponto verde com halo + mensagem curta.  
**Uso:** comunicar uma garantia operacional real.  
**Formato:** cápsula, texto de `12 px`, borda verde translúcida.  
**Seletor:** `.privacy-badge`.

### 8.3 Jornada de etapas

**Etapas:** Arquivos → Conferência → Resultado.

| Estado | Aparência |
|---|---|
| Inativo | Texto e contorno neutros |
| Ativo | Texto verde; círculo preenchido de verde |
| Concluído | Círculo verde com check branco |

O componente deve refletir o estado real do fluxo. Em telas menores, mantenha a sequência legível mesmo sem os rótulos.

### 8.4 Cartão principal

É a superfície de trabalho dominante. Use apenas um por tela. Título e ação de reinício ficam no cabeçalho; etapas, revisão e resultado compartilham o mesmo contêiner.

### 8.5 Cabeçalho de etapa

**Anatomia:** número em terracota, título e instrução auxiliar.  
**Numeração:** dois dígitos (`01`, `02`).  
**Seletor:** `.step-heading`, `.step-number`.

### 8.6 Dropzone de arquivo

**Anatomia:** ícone do formato, nome/ajuda e ação textual.

| Estado | Tratamento |
|---|---|
| Vazio | Fundo `#FBFBF7`, borda tracejada |
| Hover/arraste | Fundo `#F6FAF6`, borda sálvia, elevação de `-1 px` |
| Com arquivo | Fundo `#F4FAF6`, borda sólida e ação “Trocar arquivo” |
| Inválido | Toast de erro com motivo; não substituir o arquivo anterior |

O input nativo permanece disponível para tecnologia assistiva. Formatos aceitos e limite devem aparecer no texto auxiliar.

### 8.7 Processamento

Bloco verde-claro com spinner de `22 px`, título curto e expectativa de duração. Use `aria-live="polite"` no contêiner de status.

### 8.8 Resumo numérico

Três células para contratos, variáveis e associações. O número em verde é dominante; o rótulo é secundário. Não use para métricas sem relação direta com a tarefa atual.

### 8.9 Campos

- Rótulo sempre acima do controle.
- Altura mínima de `43 px`.
- Raio de `9 px`.
- Borda escurece no hover.
- Use texto de ajuda quando o formato esperado não for óbvio.
- Placeholder não substitui rótulo.

### 8.10 Mapeamento de variáveis

Cada linha conecta uma variável do Word à origem na planilha.

**Anatomia:** ponto de confiança, variável monoespaçada, seta e seletor de origem.

| Confiança | Cor | Significado |
|---|---:|---|
| Alta/automática | `#5F9B7E` | Associação sugerida pelo sistema |
| Média | `#D49749` | Requer atenção do usuário |
| Pendente | `--danger` | Origem ainda não definida |

Sempre mostre o estado também por texto ou contexto; o ponto colorido sozinho não é suficiente para usuários com deficiência de percepção de cor.

### 8.11 Controle segmentado

Use para até três opções mutuamente exclusivas e curtas. A opção selecionada usa superfície branca, texto verde e sombra sutil. O input de rádio nativo mantém a semântica.

### 8.12 Painel avançado

Use `<details>`/`<summary>` para opções opcionais ou de maior risco. O resumo deve informar o estado padrão. A seta gira `180°` quando o painel abre.

### 8.13 Switch

Use apenas para ligar ou desligar uma configuração com efeito imediato ou claramente descrito. Verde significa ligado; cinza significa desligado; opacidade reduzida significa indisponível.

### 8.14 Botões

#### Primário

- Um por etapa ou região.
- Fundo `--forest`, texto branco, altura mínima `50 px`.
- Hover em `--forest-dark`, elevação de `-1 px`.
- Em processamento, mantém o rótulo, exibe progresso interno e usa cursor de espera.

#### Secundário

- Fundo transparente, texto verde, borda `--line-dark`.
- Hover com borda verde e fundo `#F4F8F4`.

#### Textual

- Para ações discretas como reiniciar.
- Sem contêiner; sublinhado por borda inferior.

Rótulos começam com verbo e descrevem o resultado: “Gerar contratos e baixar ZIP”, “Criar outro lote”.

### 8.15 Resultado

Estado de sucesso centralizado, com ícone circular, kicker, título serifado, resumo e no máximo duas ações. A ação principal permite repetir o download; a secundária inicia um novo lote.

### 8.16 Toast de erro

**Anatomia:** ícone, título fixo, mensagem contextual e fechar.  
**Posição:** canto inferior direito; margem de `24 px`.  
**Duração atual:** `7 s`.  
**Semântica:** `role="alert"`.  
**Conteúdo:** diga o que impediu o avanço e, quando possível, como corrigir.

## 9. Movimento e feedback

| Interação | Duração | Curva |
|---|---:|---|
| Hover de botão | `140 ms` | `ease` |
| Dropzone | `160 ms` | `ease` |
| Jornada, switch e painel | `180 ms` | `ease` |
| Entrada do toast | `200 ms` | `ease-out` |
| Progresso do botão | `300 ms` | `ease` |
| Spinner | `700 ms` | `linear`, infinito |

- Movimento deve explicar mudança de estado, não atrasar a tarefa.
- Deslocamentos se limitam a `1–10 px`.
- Com `prefers-reduced-motion: reduce`, animações e transições caem para `0.01 ms` e uma única iteração.

## 10. Acessibilidade

- Mantenha estrutura semântica com `header`, `main`, `aside`, `section`, títulos e listas.
- Toda seção relevante deve ter título associado por `aria-labelledby` quando necessário.
- Use `aria-live="polite"` para processamento e conclusão; use `role="alert"` para falhas.
- Elementos decorativos recebem `aria-hidden="true"`.
- Controles precisam de rótulos visíveis ou nome acessível explícito.
- O foco deve permanecer visível em teclado; a cor atual é `--accent` com offset de `3 px`.
- O alvo mínimo recomendado é `44 × 44 px`; preserve as alturas atuais de campos e botões e amplie ações textuais pequenas quando necessário.
- Não dependa apenas de cor para confiança, erro, seleção ou conclusão.
- Mantenha a ordem de foco igual à ordem visual.
- Não remova o input nativo dos componentes customizados; esconda-o apenas visualmente.

## 11. Voz e conteúdo

### Princípios

- Fale com o usuário na segunda pessoa de forma respeitosa e direta.
- Prefira verbos concretos: adicionar, conferir, gerar, baixar, enviar.
- Explique a tarefa antes do detalhe técnico.
- Informe limites no ponto da decisão: “até 25 MB”, “Word .docx”.
- Reforce privacidade somente com afirmações verificáveis.
- Em mensagens de erro, evite culpa e linguagem técnica desnecessária.

### Padrões

| Situação | Padrão |
|---|---|
| Título de ação | Verbo + objeto + resultado |
| Ajuda | Formato + restrição, separados por `•` |
| Processamento | Gerúndio + expectativa curta |
| Sucesso | Resultado confirmado + próxima ação |
| Erro | Problema específico + correção possível |

### Exemplos

- **Ação:** “Gerar contratos e baixar ZIP”
- **Ajuda:** “Excel .xlsx ou .csv • até 25 MB”
- **Processamento:** “Conferindo os arquivos — isso leva só alguns segundos.”
- **Sucesso:** “Seus contratos estão prontos.”
- **Erro:** “Defina a origem de: nome, CPF e endereço.”

## 12. Tokens CSS — referência rápida

```css
:root {
  color-scheme: light;
  --ink: #17221f;
  --ink-soft: #53605c;
  --forest: #153f36;
  --forest-dark: #0d2d27;
  --sage: #dce9df;
  --sage-strong: #79a68f;
  --paper: #fffefa;
  --canvas: #f3f1e9;
  --line: #deddd5;
  --line-dark: #c9cbc3;
  --accent: #e56d4d;
  --accent-dark: #c65237;
  --success: #27735c;
  --warning: #a36520;
  --danger: #b7443e;
  --shadow: 0 18px 50px rgba(31, 42, 37, 0.09);
}
```

## 13. Checklist de novas telas

- [ ] A tela mantém uma única ação primária dominante.
- [ ] A hierarquia entre canvas, superfície e controle está clara.
- [ ] Os tokens existentes são usados antes de criar novas cores.
- [ ] Títulos editoriais são reservados para abertura ou conclusão.
- [ ] Estados de hover, foco, seleção, carregamento, sucesso, erro e indisponibilidade estão definidos.
- [ ] Textos e controles essenciais atendem ao contraste AA.
- [ ] A experiência funciona em `320 px`, `680 px`, `940 px` e desktop amplo.
- [ ] A navegação por teclado preserva foco visível e ordem lógica.
- [ ] Nenhum estado depende apenas de cor.
- [ ] A redução de movimento é respeitada.
- [ ] Limites, formatos e consequências aparecem antes da ação.
- [ ] Mensagens de erro orientam a correção.

## 14. Arquivos de origem

- `web/styles.css` — tokens, layout, componentes, estados e responsividade.
- `web/index.html` — semântica, anatomia dos componentes e conteúdo.
- `web/app.js` — transições de estado, validação, progresso e mensagens dinâmicas.

