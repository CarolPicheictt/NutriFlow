# Problemática

💡 Ideia 2 — Gestor Inteligente de Compras
Rafael: Essa aqui me parece a dor mais universal e menos atendida. Toda semana o paciente precisa comprar os ingredientes certos, nas quantidades certas.

O parser já entrega a shopping_list. Mas a gente pode ir muito além:
⌄
# O que o parser já nos dá:
shopping_list = [
  "Arroz branco cozido",
  "Banana",
  "Aveia",
  "Ovo de galinha",
  ...
]

# O que o produto pode fazer em cima disso:
→ Calcular quantidades para 7 dias de dieta
→ Agrupar por corredor de supermercado
→ Identificar o que já tem em casa (checklist)
→ Estimar custo semanal da dieta
→ Reorder automático: "você costuma comprar na quinta"
Carlos: E aqui tem uma oportunidade de receita adicional que poucas pessoas estão explorando: integração com supermercados. Rappi, iFood Mercado, Zé Delivery — todos têm API ou permitem deep link. O paciente monta a lista no app e finaliza a compra com 1 clique.

Rafael: Isso transforma o app de ferramenta em canal de distribuição. Modelo de comissão por pedido. É diferente de assinatura — escala de forma diferente.

┌─────────────────────────────────────────────────────────────┐
│  Modelo de receita potencial:                               │
│                                                             │
│  B2C: Assinatura R$14,90/mês (lista inteligente)           │
│  B2B: Comissão 2–4% sobre pedidos via integração           │
│  B2B2C: Plano para nutricionistas (R$49,90/mês)            │
│         → nutricionista oferece o app ao paciente          │
└─────────────────────────────────────────────────────────────┘
Viabilidade: ✅ Alta
Diferencial de mercado: ✅ Alto — ninguém faz isso focado em dieta prescrita
Monetização: ✅ Múltiplos vetores


💡 Ideia 3 — Planner de Marmitas Semanais
Carlos: Essa é a que eu mais gosto do ponto de vista técnico e de negócio. O Sunday meal prep é um comportamento já estabelecido em quem segue dieta. O problema é que as pessoas não sabem quanto comprar, quanto cozinhar e como organizar.

Rafael: E os dados do parser resolvem exatamente isso. Olha o que a gente consegue calcular:

Exemplo com dados reais do PDF:

Sobrecoxa de frango (almoço): 65g × 7 dias = 455g
Sobrecoxa de frango (jantar 3): 65g × 7 dias = 455g
Total frango para semana: ~910g ≈ 1kg

Arroz cozido (almoço): 150g × 7 dias = 1050g
Arroz cozido (jantar 3): 150g × 7 dias = 1050g
Total arroz cozido: ~2.1kg (≈ 700g cru)

Ovos (café + almoço + jantar 2):
(2 + 2 + 2) × 7 = 42 ovos/semana
Carlos: Isso é poderoso. O nutricionista prescreve, o app transforma em plano de produção culinária. Com passos práticos:

┌──────────────────────────────────────────────────────────┐
│  🍳 Seu Prep de Domingo                                  │
├──────────────────────────────────────────────────────────┤
│  Compras necessárias para 7 dias:                        │
│  • 1kg de sobrecoxa de frango                            │
│  • 42 ovos (3 dúzias + 6)                               │
│  • 700g de arroz cru                                     │
│  • 7 bananas                                             │
│                                                          │
│  Sequência de preparo sugerida:                          │
│  1. Cozinhe o arroz (rende as porções da semana)         │
│  2. Asse o frango (tempere antes)                        │
│  3. Cozinhe os ovos em lote                              │
│  4. Separe em 7 marmitas por refeição                    │
│                                                          │
│  ⏱️ Tempo estimado: 1h40min                              │
│  🥡 Marmitas geradas: 14                                 │
└──────────────────────────────────────────────────────────┘
Viabilidade: ✅ Alta — requer lógica de escalonamento de receitas
Diferencial de mercado: ✅ Muito Alto — não existe nada assim integrado com plano nutricional
Monetização: Assinatura + parcerias com potes/marmitas/containers


💡 Ideia 5 — Ferramenta B2B para Nutricionistas
Carlos: Rafael, todas as ideias anteriores focam no paciente. Mas tem um ângulo que a gente ainda não explorou: o nutricionista como cliente pagante.

Rafael: Explica melhor.

Carlos: O nutricionista tem 30, 50, 100 pacientes. Cada um com uma dieta diferente. Problemas reais dele:

Problemas do nutricionista hoje:
├── Paciente some após consulta e não segue a dieta
├── Não sabe se o paciente está comprando os itens certos
├── Não tem visibilidade de adesão ao plano
├── Gasta tempo respondendo "posso trocar X por Y?"
└── Sem dados para embasar ajuste na próxima consulta
Rafael: E o produto resolve exatamente isso. O nutricionista usa o WebDiet normalmente, exporta o PDF, faz upload no nosso sistema — e o paciente passa a ter o app. O nutricionista vê um painel de adesão:

┌──────────────────────────────────────────────────────┐
│  Painel do Nutricionista                             │
├──────────────────────────────────────────────────────┤
│  Carolina Picheictt                                  │
│  Adesão esta semana: 74%  ████████░░                 │
│  Refeições mais puladas: Pré-treino, Ceia            │
│  Compras realizadas: ✅ Lista completa               │
│  Próxima consulta: em 12 dias                        │
│                                                      │
│  ⚠️ Alerta: 3 dias sem registrar almoço              │
└──────────────────────────────────────────────────────┘
Carlos: Esse é o modelo B2B2C: a gente vende para o nutricionista (R$49–149/mês por plano), e ele oferece o app como diferencial para reter os pacientes. O paciente usa de graça ou com desconto.

Viabilidade: ✅ Alta
Diferencial de mercado: ✅ Alto — canal de aquisição escalável via nutricionistas
Monetização: ✅ SaaS B2B com churn baixo (nutricionista não troca de ferramenta fácil)


________________________________________________________

FASE 1 — Validação (2–3 meses)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MVP: Upload do PDF + Lista de Compras Inteligente
→ Problema mais universal, menor fricção
→ Dá para validar com 50 usuários reais
→ Não precisa de backend complexo
→ Monetização: freemium (lista básica grátis,
  quantidades semanais = pago)

FASE 2 — Retenção (3–6 meses)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
+ Notificações de refeição
+ Planner de marmitas
+ Registro de adesão
→ Aumenta DAU e justifica assinatura

FASE 3 — Escala (6–12 meses)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
+ Painel do nutricionista (B2B)
+ Integração com supermercados
+ Parceria/API com WebDiet
→ Muda o modelo de B2C para B2B2C

Rafael: Se eu precisasse resumir em uma frase: o produto é um copiloto da dieta prescrita. Não substitui o nutricionista, não cria dietas — ele pega o trabalho que o nutricionista já fez e garante que o paciente consiga executar.

Carlos: E o ponto mais importante que ficou claro nessa discussão: o PDF é a porta de entrada, mas o valor está nos comportamentos que o app cria. Comprar certo, preparar certo, comer certo, na hora certa.

O parser que a gente construiu hoje é a fundação técnica de tudo isso. E quando vier a API do WebDiet, a gente troca a ingestão sem mexer em nada do produto.

Rafael: Nome do produto?

Carlos: NutriFlow. 🥗
________________________________________________________
