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
| Calcular lista de compras para N dias (1 a 31) | `GET /api/v1/shopping/{plan_id}` |
| Consolidar alimentos duplicados entre refeições | `core/shopping/consolidator.py` |
| Normalizar nomes (lowercase, remover qualificadores como "cozido", "light" etc.) | `core/shopping/consolidator.py` |
| Classificar/converter unidades (g, kg, ml, l, unidade, "à vontade") | `core/shopping/units.py` |
| Agrupar por categoria (proteínas, carboidratos, frutas, verduras e legumes, laticínios, gorduras, outros) | `core/shopping/categorizer.py` |
| Sugestão de compra humanizada (ex.: "42 unidades (3 dúzias + 6)", "~500g") | `core/shopping/calculator.py` |
| Checklist (marcar/desmarcar item como "já tenho em casa") | `PATCH /api/v1/checklist/{plan_id}` |
| Abater ingredientes que sobraram da última compra, em gramas | Interface web e cálculo da lista |
| Escolher uma substituição por refeição, mantendo o ingrediente prescrito como padrão | `core/shopping/`, `frontend/index.html` |
| Exportar lista em texto (compartilhável) ou JSON | `GET /api/v1/shopping/{plan_id}/export` |
| Persistência de planos em JSON (`data/plans/`) e checklist em memória | `services/plan_service.py`, `services/shopping_service.py` |
| Interface web para usar todo o fluxo (upload, checklist, export) | `frontend/index.html` |
| Agrupar várias dietas da casa em uma única lista de compras | `frontend/index.html`, `services/shopping_service.py` |
| Upload de PDF do WebDiet e conversão direta para plano alimentar | `scrap_do_pdf.py`, `services/plan_service.py` |
| Meal Prep: o que cozinhar (peso cru, cozido e por marmita, com fator de cocção) e como montar lanches | `GET /api/v1/meal-prep/{plan_id}`, `core/mealprep/` |
| Base editável do Meal Prep (preparo simples por método, links de receitas) | `backend/app/data/meal_prep_base.json` |
| Tela própria do Meal Prep | botão "Meal Prep" em `frontend/index.html` |
| Testes automatizados (núcleo + rotas) | `tests/` |

### ❌ Não implementado (fora de escopo desta etapa)

- Integração real com o WebDiet (API oficial)
- Integração com supermercados / finalizar compra
- Estimativa de preços
- Painel para nutricionistas
- Histórico de compras
- Machine learning / recomendações
- Autenticação de usuários
- Aplicativo mobile
- Persistência do checklist entre reinícios (os planos são salvos em JSON;
  o checklist ainda é mantido em memória)
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
│       │       ├── shopping.py  # Rotas HTTP da lista de compras
│       │       └── meal_prep.py # Rota do Meal Prep
│       ├── core/
│       │   ├── models/
│       │   │   ├── diet_plan.py      # Reexporta DietPlan/Meal/FoodItem do parser
│       │   │   ├── shopping_list.py  # ShoppingItem, UnitType
│       │   │   └── meal_prep.py      # Modelos de saída do Meal Prep
│       │   ├── mealprep/
│       │   │   ├── catalog.py        # Consulta à base de preparo (JSON)
│       │   │   └── planner.py        # Cálculo do plano de preparo
│       │   └── shopping/
│       │       ├── calculator.py     # Orquestrador do cálculo
│       │       ├── consolidator.py   # Normalização de nomes + consolidação
│       │       ├── categorizer.py    # Agrupamento por categoria
│       │       └── units.py          # Classificação/conversão de unidades
│       ├── data/
│       │   └── meal_prep_base.json   # Preparo simples e links de receitas
│       └── services/
│           ├── plan_service.py       # Armazena planos (em memória)
│           ├── shopping_service.py   # Calcula lista, checklist, export
│           └── meal_prep_service.py  # Monta o plano de preparo
└── tests/
    ├── conftest.py
    ├── fixtures/carolina_diet.json
    ├── test_calculator.py
    ├── test_consolidator.py
    ├── test_categorizer.py
    ├── test_meal_prep_catalog.py
    ├── test_meal_prep_planner.py
    ├── test_meal_prep_api.py
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

`days` aceita valores entre 1 e 31 — fora disso a API responde `422`.

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

Você pode selecionar várias dietas no primeiro envio ou usar "Adicionar
dieta" depois de importar a primeira. Os alimentos repetidos são somados
e exibidos em uma lista única para a casa.

Quando o plano oferecer substituições, a lista mostra um seletor por
refeição e ingrediente. O item prescrito fica selecionado por padrão; ao
escolher uma alternativa, somente ela entra no cálculo e na exportação.

Use "Sobrou?" para abrir a coluna de gramas ao lado das quantidades. O valor
informado é descontado da necessidade total e salvo no navegador. Se a sobra
cobrir toda a quantidade, o item continua visível para edição, mas não aparece
no texto copiado.

O plano importado e o número de dias ficam salvos no navegador
(`localStorage`), então recarregar a página não perde o progresso do
checklist.

---

## Meal Prep

Indica o que **cozinhar e montar** para as marmitas e lanches de N dias.
Abra pelo botão "Meal Prep" na tela do plano, escolha as refeições e os dias
(padrão: 5) e gere o plano de preparo. As substituições e sobras já
informadas na lista de compras são respeitadas.

```bash
curl "http://127.0.0.1:8000/api/v1/meal-prep/{plan_id}?days=5&meal_names=Almoço"
```

Aceita os mesmos parâmetros da lista de compras: `meal_names`,
`additional_plan_ids`, `substitution_choices` e `leftovers_grams`.

**Itens que vão ao fogo** (frango, arroz, legumes, ovos...) trazem o peso cru a
cozinhar, o peso cozido esperado e a quantidade por marmita, calculados com a
planilha de fatores de cocção (`docs/cooking_factors_dieta.xlsx`). O peso cru é
sempre arredondado para cima, em gramas inteiras. Se não houver fator
confiável, a quantidade da dieta é mantida e o item recebe um aviso. Exemplo
(valores hipotéticos): 120 g de frango grelhado por dia, por 5 dias, viram
600 g cozidos, ou cerca de 834 g crus.

**Itens que não vão ao fogo** (iogurte, fruta, aveia...) aparecem na montagem de
cada refeição, com uma frase simples, como "Misture iogurte natural, banana e
aveia em flocos em um recipiente e consuma." Os pesos desses itens não passam
pelo fator de cocção.

### Editando a base de preparo

O preparo mais simples e as sugestões ficam em
[`backend/app/data/meal_prep_base.json`](backend/app/data/meal_prep_base.json):

- `methods`: passos por método de cocção (as chaves são as da coluna
  `cooking_method` da planilha de fatores);
- `foods`: quais alimentos vão ao fogo (`cook`) ou só são montados
  (`assemble`), por palavra-chave, e os links de receitas da internet de cada
  um. Vale a primeira entrada cujas palavras-chave aparecem no nome;
- `assembly`: modelos de frase para lanches e marmitas.

Os links foram coletados em buscas na web e não são verificados
automaticamente; confira se continuam no ar ao editar a base. O Meal Prep
mostra só o título e o link de cada receita, sem copiar o texto.

---

## Observações importantes

- **Persistência parcial**: os planos ficam em `data/plans/` e sobrevivem
  ao reinício da API. O checklist ainda vive em memória e é reiniciado com
  o processo.
- **Unidades incompatíveis não são somadas**: se o mesmo alimento aparecer
  como "100 g" numa refeição e "2 unidades" em outra, o NutriFlow mantém
  a primeira quantidade e não faz uma soma sem sentido — isso é
  intencional e coberto por teste.
- **Normalização de nomes é simples (MVP)**: remove espaços extras,
  lowercase e qualificadores comuns ("cozido", "light", "integral" etc.).
  Não há stemming nem IA semântica nesta versão.


Terminal 1, backend:
python -m uvicorn app.main:app --reload --app-dir backend

Terminal 2, frontend:
python -m http.server 5500 --directory frontend

Depois abra http://localhost:5500. O Swagger do backend fica em http://127.0.0.1:8000/docs.