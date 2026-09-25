# NutriFlow 🥗

Transforma um plano alimentar **já prescrito** por um nutricionista em uma
lista de compras inteligente — calcula quantidades para N dias, consolida
alimentos repetidos, agrupa por categoria e permite marcar o que você já
tem em casa.

> NutriFlow **não cria dietas** e **não substitui o nutricionista**. Ele
> parte de um plano alimentar exportado do WebDiet (JSON) e ajuda a
> executar esse plano nas compras.

A ideia original de produto (visão de negócio, monetização, fases
futuras) está documentada em [`docs/brainstorm-produto.md`](docs/brainstorm-produto.md).
Este README cobre o que **existe e funciona hoje**.

---

## Escopo

### ✅ Implementado

| Funcionalidade | Onde |
|---|---|
| Receber plano alimentar em JSON | `POST /api/v1/upload` |
| Calcular lista de compras para N dias (1 a 30) | `GET /api/v1/shopping/{plan_id}` |
| Consolidar alimentos duplicados entre refeições | `core/shopping/consolidator.py` |
| Normalizar nomes (lowercase, remover qualificadores como "cozido", "light" etc.) | `core/shopping/consolidator.py` |
| Classificar/converter unidades (g, kg, ml, l, unidade, "à vontade") | `core/shopping/units.py` |
| Agrupar por categoria (proteínas, carboidratos, frutas, verduras e legumes, laticínios, gorduras, outros) | `core/shopping/categorizer.py` |
| Sugestão de compra humanizada (ex.: "42 unidades (3 dúzias + 6)", "~500g") | `core/shopping/calculator.py` |
| Checklist (marcar/desmarcar item como "já tenho em casa") | `PATCH /api/v1/checklist/{plan_id}` |
| Exportar lista em texto (compartilhável) ou JSON | `GET /api/v1/shopping/{plan_id}/export` |
| Armazenamento em memória, pronto para trocar por banco depois | `services/plan_service.py`, `services/shopping_service.py` |
| Interface web para usar todo o fluxo (upload, checklist, export) | `frontend/index.html` |
| Parser de PDF do WebDiet → JSON (script separado, tratado como dependência externa) | `scrap_do_pdf.py` |
| Testes automatizados (núcleo + rotas) | `tests/` |

### ❌ Não implementado (fora de escopo desta etapa)

- Upload de PDF diretamente pela API (a rota já valida e retorna `501`,
  mas a extração real ainda não está ligada — o parser existe em
  `scrap_do_pdf.py` e pode ser plugado depois)
- Integração real com o WebDiet (API oficial)
- Integração com supermercados / finalizar compra
- Estimativa de preços
- Painel para nutricionistas
- Histórico de compras
- Machine learning / recomendações
- Autenticação de usuários
- Aplicativo mobile
- Persistência real (PostgreSQL, Redis) — hoje tudo é em memória e
  **reseta quando o processo reinicia**
- Pagamentos / assinaturas

---

## Estrutura do projeto

```
NutriFlow/
├── scrap_do_pdf.py              # Parser do PDF do WebDiet → DietPlan (dependência externa)
├── requirements.txt
├── pytest.ini
├── frontend/
│   └── index.html               # Interface web (HTML/CSS/JS puro, sem build)
├── docs/
│   └── brainstorm-produto.md    # Ideação de produto/negócio original
├── backend/
│   └── app/
│       ├── main.py              # Entrypoint FastAPI
│       ├── api/
│       │   ├── dependencies.py  # Injeção dos serviços (singletons em memória)
│       │   └── routes/
│       │       └── shopping.py  # Rotas HTTP
│       ├── core/
│       │   ├── models/
│       │   │   ├── diet_plan.py      # Reexporta DietPlan/Meal/FoodItem do parser
│       │   │   └── shopping_list.py  # ShoppingItem, UnitType
│       │   └── shopping/
│       │       ├── calculator.py     # Orquestrador do cálculo
│       │       ├── consolidator.py   # Normalização de nomes + consolidação
│       │       ├── categorizer.py    # Agrupamento por categoria
│       │       └── units.py          # Classificação/conversão de unidades
│       └── services/
│           ├── plan_service.py       # Armazena planos (em memória)
│           └── shopping_service.py   # Calcula lista, checklist, export
└── tests/
    ├── conftest.py
    ├── fixtures/carolina_diet.json
    ├── test_calculator.py
    ├── test_consolidator.py
    ├── test_categorizer.py
    └── test_api.py
```

---

## Passo a passo — rodando localmente

### 1. Instalar dependências

```bash
pip install -r requirements.txt
```

### 2. Rodar os testes

```bash
pytest
```

Deve mostrar algo como `28 passed`.

### 3. Subir a API

```bash
python -m uvicorn app.main:app --reload --app-dir backend
```

A API sobe em `http://127.0.0.1:8000`. Documentação interativa (Swagger)
em `http://127.0.0.1:8000/docs`.

### 4. Fazer upload de um plano alimentar

Use um JSON de plano alimentar (ex.: `tests/fixtures/carolina_diet.json`,
gerado a partir de um PDF real do WebDiet pelo parser `scrap_do_pdf.py`):

```bash
curl -X POST http://127.0.0.1:8000/api/v1/upload \
  -F "file=@tests/fixtures/carolina_diet.json;type=application/json"
```

Resposta:

```json
{
  "plan_id": "8f1e2c...-...",
  "patient_name": "Carolina Picheictt",
  "meals_found": 7,
  "message": "Plano importado com sucesso"
}
```

Guarde o `plan_id` — ele é necessário nos próximos passos.

### 5. Calcular a lista de compras

```bash
curl "http://127.0.0.1:8000/api/v1/shopping/{plan_id}?days=7"
```

Retorna os itens já consolidados, escalonados para 7 dias e agrupados por
categoria (`proteínas`, `carboidratos`, `frutas`, `verduras e legumes`,
`laticínios`, `gorduras`, `outros`).

`days` aceita valores entre 1 e 30 — fora disso a API responde `422`.

### 6. Marcar um item como "já tenho em casa"

```bash
curl -X PATCH http://127.0.0.1:8000/api/v1/checklist/{plan_id} \
  -H "Content-Type: application/json" \
  -d '{"item_name": "Arroz branco", "checked": true}'
```

O estado do checklist é por alimento (independe do número de dias
escolhido) e vale para as próximas consultas à lista desse plano.

### 7. Exportar a lista

Texto pronto para compartilhar:

```bash
curl "http://127.0.0.1:8000/api/v1/shopping/{plan_id}/export?days=7&fmt=text"
```

JSON estruturado:

```bash
curl "http://127.0.0.1:8000/api/v1/shopping/{plan_id}/export?days=7&fmt=json"
```

---

## Front-end

Em vez de usar `curl`, você pode usar a interface web em
[`frontend/index.html`](frontend/index.html) — um único arquivo HTML, sem
build nem dependências, que cobre todo o fluxo acima (upload, dias,
checklist com progresso, copiar/baixar a lista).

1. Suba a API normalmente (passo 3 acima). Ela já vem com CORS liberado
   para uso local.
2. Abra `frontend/index.html` diretamente no navegador (duplo clique) —
   ou sirva a pasta com `python -m http.server 5500` dentro de `frontend/`
   e acesse `http://localhost:5500`.
3. Se a API não estiver em `http://127.0.0.1:8000`, ajuste o endereço no
   link "Endereço da API" no topo da página.

O plano importado e o número de dias ficam salvos no navegador
(`localStorage`), então recarregar a página não perde o progresso do
checklist.

---

## Observações importantes

- **Sem persistência real**: os planos e o checklist vivem em memória do
  processo. Reiniciar a API apaga tudo. As interfaces (`PlanRepository`,
  `ChecklistRepository`) já estão desenhadas para permitir trocar por
  PostgreSQL sem alterar os serviços ou as rotas.
- **Unidades incompatíveis não são somadas**: se o mesmo alimento aparecer
  como "100 g" numa refeição e "2 unidades" em outra, o NutriFlow mantém
  a primeira quantidade e não faz uma soma sem sentido — isso é
  intencional e coberto por teste.
- **Normalização de nomes é simples (MVP)**: remove espaços extras,
  lowercase e qualificadores comuns ("cozido", "light", "integral" etc.).
  Não há stemming nem IA semântica nesta versão.
