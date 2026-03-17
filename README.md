# finance-data-platform

🚧 **Project in development**

Ferramenta em desenvolvimento para **reduzir o tempo necessário na manutenção de carteiras, gestão e escolha de ativos**, automatizando a leitura e síntese de documentos oficiais do mercado financeiro.

O objetivo é ajudar **investidores iniciantes e intermediários** a identificar rapidamente:

- o momento atual de um ativo  
- mudanças relevantes  
- pontos de atenção  
- urgência de leitura de relatórios completos  

---

# Problema

A gestão de uma carteira exige acompanhamento constante de documentos como:

- relatórios gerenciais  
- fatos relevantes  
- comunicados ao mercado  
- documentos regulatórios  

Esses materiais geralmente são:

- extensos  
- técnicos  
- publicados com frequência  

Como resultado, muitos investidores acabam:

- gastando **horas lendo relatórios**
- ou **desistindo** de investir pelo tempo necessário

---

# Proposta do Projeto

Este projeto busca **automatizar a análise desses documentos**, gerando uma **síntese estruturada da tese do ativo**.

A ferramenta pretende:

- coletar informações de **fontes oficiais**
- extrair os pontos mais relevantes
- apresentar um **resumo objetivo da tese**
- indicar se existe **urgência na leitura do documento completo**
- explicar conceitos quando necessário

 ⚠️ O objetivo não é substituir a leitura completa, mas **priorizar o que realmente merece atenção**.

---

# ⚙️ Arquitetura do MVP

O projeto foi redesenhado com foco em um **MVP funcional**, priorizando a entrega de valor com o menor overhead possível.

### Pipeline atual (MVP)
Input de Documentos (manual)
↓
Extração de Texto
↓
Módulo de Resumo (CORE)
↓
Geração de Tese
↓
Envio por Email


### Descrição dos módulos

#### 📥 Input de Documentos
Inicialmente, os documentos são obtidos manualmente (relatórios, fatos relevantes, etc.).

Futuramente, este processo será automatizado via web crawler.

---

#### 🧠 Módulo de Resumo (CORE)

O núcleo do projeto é baseado em **modelos de linguagem (LLMs)** integrados via API, utilizando técnicas de **engenharia de prompt** para extrair e estruturar informações relevantes de documentos financeiros.

##### Como funciona

O processamento segue uma abordagem estruturada:

1. Extração do texto do documento
2. Segmentação do conteúdo (quando necessário)
3. Aplicação de prompts específicos para:
   - identificação da tese do ativo
   - detecção de mudanças relevantes
   - extração de pontos de atenção
4. Geração de um resumo estruturado e objetivo

---

##### Engenharia de Prompt

Os prompts são projetados para:

- reduzir ruído e informações irrelevantes  
- forçar respostas estruturadas  
- manter consistência entre diferentes documentos  
- evitar interpretações subjetivas excessivas  

Exemplo de abordagem:

- instruções claras de papel ("analista de investimentos")
- definição de formato de saída
- foco em mudanças e riscos
- restrição a informações presentes no documento

---

##### Desafios

Alguns desafios considerados no desenvolvimento:

- variação no formato dos documentos  
- linguagem técnica do mercado financeiro  
- risco de alucinação dos modelos  
- necessidade de consistência entre análises  

---

##### Decisão de Engenharia

O uso de LLMs foi escolhido por permitir:

- alta flexibilidade na análise de textos não estruturados  
- rápida evolução do sistema  
- adaptação a diferentes tipos de documentos  

Sem necessidade inicial de modelos treinados do zero.

#### 📤 Envio de Relatórios

Após a análise, o sistema:

- organiza o conteúdo gerado
- envia um resumo estruturado por email

Objetivo:
> entregar informação relevante de forma rápida e consumível

---

# 🚧 Evolução Planejada

A arquitetura foi pensada para evoluir de forma incremental:

### Próximos módulos

- [ ] Web Crawler (coleta automatizada de documentos)
- [ ] Módulo de Armazenamento
- [ ] API REST
- [ ] Interface Web (Frontend)

---

# 🧭 Decisão de Engenharia

O escopo foi reduzido intencionalmente para priorizar:

- entrega rápida de valor
- foco no problema principal (análise de documentos)
- desenvolvimento incremental

Em vez de construir toda a infraestrutura inicialmente, o projeto foca primeiro no **core de inteligência**, expandindo os demais módulos posteriormente.
